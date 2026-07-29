-- yoyo migration script
ALTER TABLE cv
ADD times_opened_by_guests integer NOT NULL DEFAULT 0;