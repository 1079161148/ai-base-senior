-- 0002 增量迁移：新增置顶能力
-- 【要点】ALTER TABLE 只能加列/改名，不要在迁移里重建表再用 INSERT SELECT
ALTER TABLE notes ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0;