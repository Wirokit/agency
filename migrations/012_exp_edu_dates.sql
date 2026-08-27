-- yoyo migration script
ALTER TABLE cv_job_experiences
ADD start_date date;

ALTER TABLE cv_job_experiences
ADD end_date date;

ALTER TABLE cv_educations
ADD start_date date;

ALTER TABLE cv_educations
ADD end_date date;

ALTER TABLE cv_job_experiences
DROP time_period;

ALTER TABLE cv_educations
DROP time_period;
