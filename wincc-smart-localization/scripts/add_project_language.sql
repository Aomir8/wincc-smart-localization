DECLARE @culture nvarchar(85) = @TARGET_CULTURE@;
DECLARE @slot int = @TARGET_SLOT@;
DECLARE @template uniqueidentifier = @PROJECT_LANGUAGE_TEMPLATE@;
DECLARE @languageId uniqueidentifier = NEWID(), @now datetime = GETUTCDATE();

IF EXISTS (
    SELECT 1 FROM dbo.HmiProjectLanguageTable l JOIN dbo.HmiBasicTable b ON b.ObjId=l.Id
    JOIN dbo.HmiBasicTable f ON f.ObjId=b.ParentId AND f.ObjName='HmiProjectLanguageFolder'
    WHERE l.LanguageNumber=@slot OR (b.ObjName=@culture AND b.Deleted=0 AND b.Destroyed=0)
) OR EXISTS (SELECT 1 FROM dbo.HmiTextTable WHERE DATALENGTH(@SLOT_COLUMN@)>0)
  OR EXISTS (SELECT 1 FROM dbo.HmiFontListTable WHERE DATALENGTH(@SLOT_COLUMN@)>0)
  OR EXISTS (SELECT 1 FROM dbo.HmiImageDataTable WHERE @SLOT_COLUMN@ IS NOT NULL)
    THROW 50001, 'The target culture or slot is no longer free.', 1;

INSERT dbo.HmiBasicTable
    (ObjId, ObjName, ParentId, ObjParentTypeCode, ObjTypeCode, CreateTime, LastModified,
     Deleted, Destroyed, Undeletable, Constant, Internal, TmpSessionId, ObjMajorVersion,
     ObjMinorVersion, Created, Modified, Locked, SessionId, ForwardRefs, DeviceNumber,
     ContainerId, ContainerType, Prototype)
SELECT @languageId, @culture, ParentId, ObjParentTypeCode, ObjTypeCode, @now, @now,
       0, 0, 0, 0, 0, -1, ObjMajorVersion, ObjMinorVersion, 1, NULL, NULL, -1,
       NULL, DeviceNumber, NULL, NULL, 0
FROM dbo.HmiBasicTable WHERE ObjId=@template AND Deleted=0 AND Destroyed=0;
IF @@ROWCOUNT<>1 THROW 50001, 'The project language template is missing.', 1;

INSERT dbo.HmiProjectLanguageTable (LanguageNumber, Id, FkColSessionId) VALUES (@slot,@languageId,-1);

CREATE TABLE #FontTemplates (Id uniqueidentifier PRIMARY KEY, NewId uniqueidentifier NOT NULL DEFAULT NEWID());
-- FONT_TEMPLATES

INSERT dbo.HmiBasicTable
    (ObjId, ObjName, ParentId, ObjParentTypeCode, ObjTypeCode, CreateTime, LastModified,
     Deleted, Destroyed, Undeletable, Constant, Internal, TmpSessionId, ObjMajorVersion,
     ObjMinorVersion, Created, Modified, Locked, SessionId, ForwardRefs, DeviceNumber,
     ContainerId, ContainerType, Prototype)
SELECT t.NewId, @culture, b.ParentId, b.ObjParentTypeCode, b.ObjTypeCode, @now, @now,
       0, 0, 0, 0, 0, -1, b.ObjMajorVersion, b.ObjMinorVersion, 1, NULL, NULL, -1,
       NULL, b.DeviceNumber, NULL, NULL, 0
FROM #FontTemplates t JOIN dbo.HmiBasicTable b ON b.ObjId=t.Id AND b.Deleted=0 AND b.Destroyed=0;
IF @@ROWCOUNT<>(SELECT COUNT(*) FROM #FontTemplates) THROW 50001, 'A device font template is missing.', 1;

INSERT dbo.HmiDeviceLanguageFontSettingTable (DefaultFont, ConfiguredFontFamilyNames, Id, FkColSessionId, FontInstallable)
SELECT NULL, 0x5574616821000000000B01010401010101, NewId, -1, 0 FROM #FontTemplates;

UPDATE f SET @SLOT_COLUMN@=COALESCE(@FONT_FALLBACK_COLUMNS@,NULL)
FROM dbo.HmiFontListTable f JOIN dbo.HmiBasicTable b ON b.ObjId=f.Id
WHERE b.Deleted=0 AND b.Destroyed=0 AND b.Prototype=0 AND f.@SLOT_COLUMN@ IS NULL
  AND COALESCE(@FONT_FALLBACK_COLUMNS@,NULL) IS NOT NULL;
