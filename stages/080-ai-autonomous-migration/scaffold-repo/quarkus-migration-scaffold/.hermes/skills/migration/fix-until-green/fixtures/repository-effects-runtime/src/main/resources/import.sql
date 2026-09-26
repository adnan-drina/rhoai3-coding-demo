-- one row the application never wrote: reads are proven on it even when writes are no-ops
insert into crate (id, name) values (1000, 'seeded');
