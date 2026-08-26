-- yoyo migration script
ALTER TABLE cv_job_experiences
ADD start_date date;

ALTER TABLE cv_job_experiences
ADD end_date date;

ALTER TABLE cv_job_experiences
ADD start_is_year boolean NOT NULL DEFAULT false;

ALTER TABLE cv_job_experiences
ADD end_is_year boolean NOT NULL DEFAULT false;

ALTER TABLE cv_educations
ADD start_date date;

ALTER TABLE cv_educations
ADD end_date date;

ALTER TABLE cv_educations
ADD start_is_year boolean NOT NULL DEFAULT false;

ALTER TABLE cv_educations
ADD end_is_year boolean NOT NULL DEFAULT false;