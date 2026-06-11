-- yoyo migration script
CREATE TABLE cv_profile_texts
(
    id serial PRIMARY KEY,
    cv_id uuid NOT NULL,
    profile_text text COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT cv_profile_texts_cv_id_fkey FOREIGN KEY (cv_id)
        REFERENCES public.cv (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
)
