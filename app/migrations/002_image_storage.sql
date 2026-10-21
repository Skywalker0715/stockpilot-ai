-- 002_image_storage.sql: app-managed image upload storage (additive only).
-- Existing rows keep stored_path NULL, meaning "no uploaded image".
-- stored_path is a server-generated filename inside the uploads directory;
-- clients can never supply or read arbitrary paths.

ALTER TABLE assets ADD COLUMN stored_path TEXT;
ALTER TABLE assets ADD COLUMN original_filename TEXT;
ALTER TABLE assets ADD COLUMN width INTEGER;
ALTER TABLE assets ADD COLUMN height INTEGER;
ALTER TABLE assets ADD COLUMN file_size INTEGER;
