-- yoyo migration script
ALTER TABLE cv_job_experiences
ADD start_display_month boolean NOT NULL DEFAULT True;

ALTER TABLE cv_job_experiences
ADD end_display_month boolean NOT NULL DEFAULT True;

ALTER TABLE cv_educations
ADD start_display_month boolean NOT NULL DEFAULT True;

ALTER TABLE cv_educations
ADD end_display_month boolean NOT NULL DEFAULT True;
