-- yoyo migration script
-- depends: 013_exp_edu_date_display
ALTER TABLE users
ADD session_version bigint NOT NULL DEFAULT 0;
