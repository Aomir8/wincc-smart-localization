import hashlib
import html
import re
import struct


EMPTY_TABLE = b"Utah!\x00\x00\x00\x00\x01\x19\x00"
TAG = r"</?[A-Za-z_][\w:.-]*(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>"
MARKUP = re.compile(r"^\s*<text(?:\s|/?>)", re.IGNORECASE)
PROTECTED = re.compile(
    r"@\d+[A-Za-z]*%[^@\r\n]+@"
    r"|&(?:\#[0-9]+|\#x[0-9a-fA-F]+|[A-Za-z][\w]+);"
    r"|\$\{[^{}\r\n]+\}|\{\{[^{}\r\n]+\}\}|\{\d+(?:[^{}\r\n]*)\}|\{[A-Za-z_][\w.]*\}"
    r"|%%|%\([\w.]+\)[sdif]|%\d+\$[sdif]|%[-+0-9.#]*[sdifxX]|%\d+"
    r"|(?<!\w)%?(?:DB\d+\.DB[XBWD]|AIW|AQW|SM[ BWD]?|[IQMV][BWD]?|[TCS])\d+(?:\.\d+)?(?!\w)"
    r"|\r\n|[\r\n\t]"
)
CODE = re.compile(r"(?:[A-Z]|PLC|HMI|I/O|[A-Z]+\d+[A-Z0-9._/-]*|\d+(?:[.,]\d+)?)$")


def read_length(blob, index):
    length = 0
    for shift in range(0, 35, 7):
        part = blob[index]
        index += 1
        length |= (part & 127) << shift
        if part < 128:
            return length, index
    raise ValueError("invalid string length")


def write_length(length):
    result = bytearray()
    while length >= 128:
        result.append((length & 127) | 128)
        length >>= 7
    result.append(length)
    return result


def decode(blob):
    if blob in (None, EMPTY_TABLE):
        return [], []
    if len(blob) < 15 or blob[:5] != b"Utah!" or blob[9:11] != b"\x01\x19":
        raise ValueError("unsupported WinCC text data encoding")
    count = blob[11]
    position = 12 + 4 * count
    if blob[position:position + 2] != b"\x01S":
        raise ValueError("unsupported WinCC string table")
    refs = []
    for i in range(12, position, 4):
        if blob[i] != 0 or blob[i + 2] != 0:
            raise ValueError("unsupported WinCC string reference")
        refs.append([blob[i + 1] - 2, blob[i + 3] - 2])
    try:
        string_count, position = read_length(blob, position + 2)
        strings = []
        for _ in range(string_count):
            size, position = read_length(blob, position)
            strings.append(blob[position:position + size].decode("utf-8"))
            position += size
    except (IndexError, UnicodeDecodeError) as error:
        raise ValueError("invalid WinCC string table") from error
    if position != len(blob) or any(not 0 <= i < len(strings) for pair in refs for i in pair):
        raise ValueError("invalid WinCC string table boundaries")
    keys = [strings[key].casefold() for key, _ in refs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate language in a WinCC text record")
    if encode(strings, refs) != blob:
        raise ValueError("WinCC text data did not round-trip byte-for-byte")
    return strings, refs


def encode(strings, refs):
    if not strings and not refs:
        return EMPTY_TABLE
    if len(strings) > 254 or len(refs) > 255:
        raise ValueError("WinCC string table exceeds this encoding's limits")
    payload = bytearray(b"Utah!" + struct.pack("<I", 12 + 4 * len(refs)) + bytes([1, 25, len(refs)]))
    for key, value in refs:
        payload.extend((0, key + 2, 0, value + 2))
    payload.extend(b"\x01S")
    payload.extend(write_length(len(strings)))
    for string in strings:
        encoded = string.encode("utf-8")
        payload.extend(write_length(len(encoded)))
        payload.extend(encoded)
    return bytes(payload)


def language_values(strings, refs):
    return {strings[key].casefold(): strings[value] for key, value in refs}


def replace_value(blob, culture, text):
    strings, refs = decode(blob)
    if text not in strings:
        strings.append(text)
    index = strings.index(text)
    for pair in refs:
        if strings[pair[0]].casefold() == culture.casefold():
            pair[1] = index
            break
    else:
        if culture not in strings:
            strings.append(culture)
        refs.append([strings.index(culture), index])
    result = encode(strings, refs)
    decode(result)
    return result


def wincc_hash(cultures, values):
    data = "".join(f"{culture}|{values.get(culture.casefold(), '')}" for culture in cultures)
    return struct.unpack(">iiii", hashlib.md5(data.encode("utf-8"), usedforsecurity=False).digest())


def plain_text(text):
    if not MARKUP.match(text):
        return text
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    return html.unescape(re.sub(TAG, "", text))


def translation_parts(text):
    marked_up = bool(MARKUP.match(text))
    pattern = re.compile(f"{TAG}|{PROTECTED.pattern}") if marked_up else PROTECTED
    layout = []
    end = 0
    for match in pattern.finditer(text):
        layout.append((text[end:match.start()], False))
        layout.append((match.group(), True))
        end = match.end()
    layout.append((text[end:], False))
    result = []
    for value, protected in layout:
        stripped = value.strip()
        if protected or not any(c.isalpha() for c in stripped) or CODE.fullmatch(stripped):
            result.append((value, True))
            continue
        start = len(value) - len(value.lstrip())
        end = len(value.rstrip())
        result.extend(((value[:start], True), (stripped, False), (value[end:], True)))
    return result


def render_translation(source, translated_parts):
    layout = translation_parts(source)
    if isinstance(translated_parts, str):
        translated_parts = [translated_parts]
    if not isinstance(translated_parts, list) or len(translated_parts) != sum(not fixed for _, fixed in layout):
        raise ValueError("translation segment count does not match the inventory")
    parts = iter(translated_parts)
    formatted = bool(MARKUP.match(source))
    result = []
    for literal, fixed in layout:
        if fixed:
            result.append(literal)
        else:
            translated = next(parts)
            if (not isinstance(translated, str) or not translated.strip() or translated != translated.strip()
                    or any(ord(c) < 32 for c in translated) or PROTECTED.search(translated)):
                raise ValueError("a translated segment is blank or introduces layout, a placeholder, or an address")
            result.append(html.escape(translated, quote=False) if formatted else translated)
    return "".join(result)
