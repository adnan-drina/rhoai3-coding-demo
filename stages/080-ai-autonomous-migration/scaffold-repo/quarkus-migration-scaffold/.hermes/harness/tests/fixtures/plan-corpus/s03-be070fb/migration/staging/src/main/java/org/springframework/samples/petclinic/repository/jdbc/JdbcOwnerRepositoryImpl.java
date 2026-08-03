package org.springframework.samples.petclinic.repository.jdbc;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class JdbcOwnerRepositoryImpl {
  @Autowired
  private NamedParameterJdbcTemplate jdbc;

  private final JdbcPetRowMapper petRowMapper = new JdbcPetRowMapper();
  private final JdbcVisitRowMapper visitRowMapper = new JdbcVisitRowMapper();

  public void loadPets(JdbcPet pet, JdbcPetVisitExtractor extractor)
      throws DataAccessException {
    petRowMapper.mapRow(null, 0);
    visitRowMapper.mapRow(null, 0);
    extractor.extractData(null);
  }
}
