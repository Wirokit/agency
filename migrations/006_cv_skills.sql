-- yoyo migration script
CREATE TABLE cv_skills
(
    cv_id uuid NOT NULL,
    skill_id integer NOT NULL,
    proficiency integer NOT NULL,
    is_highlight boolean DEFAULT false,
    CONSTRAINT cv_skills_pkey PRIMARY KEY (cv_id, skill_id),
    CONSTRAINT cv_skills_cv_id_fkey FOREIGN KEY (cv_id)
        REFERENCES public.cv (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT cv_skills_skill_id_fkey FOREIGN KEY (skill_id)
        REFERENCES public.skills (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT cv_skills_proficiency_check CHECK (proficiency >= 1 AND proficiency <= 5)
)
