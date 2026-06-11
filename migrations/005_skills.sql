-- yoyo migration script
CREATE TABLE skills
(
    id SERIAL PRIMARY KEY,
    name character varying(255) COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT skills_name_key UNIQUE (name)
)
