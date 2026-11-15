SET NOCOUNT ON;

SELECT Id, CONVERT(varbinary(max),ProjectMetaVersion) AS Metadata FROM dbo.HmiProjectTable;

SELECT b.ObjId AS Id, b.ObjName AS Culture, l.LanguageNumber AS Slot,
       b.Deleted, b.Destroyed, b.ParentId AS FolderId
FROM dbo.HmiProjectLanguageTable l JOIN dbo.HmiBasicTable b ON b.ObjId=l.Id
JOIN dbo.HmiBasicTable f ON f.ObjId=b.ParentId AND f.ObjName='HmiProjectLanguageFolder'
WHERE f.Deleted=0 AND f.Destroyed=0
ORDER BY l.LanguageNumber,b.ObjId;

SELECT b.ObjId AS Id, b.ObjName AS Culture, l.DownloadOrder
FROM dbo.HmiOnlineLanguageTable l JOIN dbo.HmiBasicTable b ON b.ObjId=l.Id
JOIN dbo.HmiBasicTable f ON f.ObjId=b.ParentId AND f.ObjName='HmiOnlineLanguageFolder'
WHERE b.Deleted=0 AND b.Destroyed=0 ORDER BY b.ObjId;

SELECT s.ReferenceLanguageName AS ReferenceCulture, s.EditingLanguageName AS EditingCulture
FROM dbo.HmiProjectLanguageSettingsTable s JOIN dbo.HmiBasicTable b ON b.ObjId=s.Id
WHERE b.ObjName='HmiProjectLanguageSettings' AND b.Deleted=0 AND b.Destroyed=0;

SELECT t.name AS TableName, c.name AS ColumnName, c.max_length AS MaxBytes,
       TYPE_NAME(c.user_type_id) AS TypeName
FROM sys.tables t JOIN sys.columns c ON t.object_id=c.object_id
WHERE t.schema_id=SCHEMA_ID('dbo') AND t.name IN ('HmiTextTable','HmiFontListTable','HmiImageDataTable')
  AND c.name LIKE 'Language%';

SELECT f.ObjId AS FolderId, b.ObjName AS Culture, s.Id, s.DefaultFont,
       CONVERT(varbinary(max),s.ConfiguredFontFamilyNames) AS FontNames, s.FontInstallable
FROM dbo.HmiBasicTable f
LEFT JOIN dbo.HmiBasicTable b ON b.ParentId=f.ObjId AND b.Deleted=0 AND b.Destroyed=0
LEFT JOIN dbo.HmiDeviceLanguageFontSettingTable s ON s.Id=b.ObjId
WHERE f.ObjName='HmiDeviceLanguageFontSettingFolder' AND f.Deleted=0 AND f.Destroyed=0
ORDER BY f.ObjId,b.ObjName;

-- OCCUPIED_SLOTS

SELECT f.*, CASE WHEN b.Deleted=0 AND b.Destroyed=0 AND b.Prototype=0 THEN 1 ELSE 0 END AS Active
FROM dbo.HmiFontListTable f LEFT JOIN dbo.HmiBasicTable b ON b.ObjId=f.Id ORDER BY f.Id;

SELECT t.*, b.ObjName AS ObjectName, p.ObjName AS ParentName, g.ObjName AS GrandparentName,
       gg.ObjName AS GreatGrandparentName, b.ParentId AS ParentId
FROM dbo.HmiTextTable t
JOIN dbo.HmiBasicTable b ON b.ObjId=t.Id AND b.Deleted=0 AND b.Destroyed=0 AND b.Prototype=0
LEFT JOIN dbo.HmiBasicTable p ON p.ObjId=b.ParentId
LEFT JOIN dbo.HmiBasicTable g ON g.ObjId=p.ParentId
LEFT JOIN dbo.HmiBasicTable gg ON gg.ObjId=g.ParentId
WHERE ISNULL(t.IsHiddenText,0)=0 AND ISNULL(t.IsSystemMessageText,0)=0
ORDER BY t.Id;
