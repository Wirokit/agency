-- yoyo migration script
CREATE TABLE cv_educations
(
    id SERIAL PRIMARY KEY,
    cv_id uuid NOT NULL,
    degree character varying(255) COLLATE pg_catalog."default" NOT NULL,
    school character varying(255) COLLATE pg_catalog."default" NOT NULL,
    time_period character varying(100) COLLATE pg_catalog."default",
    description text COLLATE pg_catalog."default",
    CONSTRAINT cv_educations_cv_id_fkey FOREIGN KEY (cv_id)
        REFERENCES public.cv (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
)
