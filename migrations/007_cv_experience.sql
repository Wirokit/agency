-- yoyo migration script
CREATE TABLE cv_job_experiences
(
    id SERIAL PRIMARY KEY,
    cv_id uuid NOT NULL,
    title character varying(255) COLLATE pg_catalog."default" NOT NULL,
    company_name character varying(255) COLLATE pg_catalog."default",
    time_period character varying(100) COLLATE pg_catalog."default",
    description text COLLATE pg_catalog."default",
    CONSTRAINT cv_job_experiences_cv_id_fkey FOREIGN KEY (cv_id)
        REFERENCES public.cv (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
)
