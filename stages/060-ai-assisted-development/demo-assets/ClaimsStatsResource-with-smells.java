package com.parasol;

import java.util.HashMap;
import java.util.Map;

import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

@Path("/api/claims/stats")
@Produces(MediaType.APPLICATION_JSON)
public class ClaimsStatsResource {

	@Inject
	ClaimsResource claimsResource;

	@GET
	public Map<String, Object> getStats() {
		Map<String, Object> stats = new HashMap<>();

		System.out.println("Fetching claim statistics");

		try {
			var claims = claimsResource.getAllClaims();
			stats.put("total", claims.size());

			Map<String, Long> byCategory = new HashMap<>();
			for (var claim : claims) {
				byCategory.merge(claim.getCategory(), 1L, Long::sum);
			}
			stats.put("by_category", byCategory);

			Map<String, Long> byStatus = new HashMap<>();
			for (var claim : claims) {
				byStatus.merge(claim.getStatus(), 1L, Long::sum);
			}
			stats.put("by_status", byStatus);
		} catch (Exception e) {
		}

		return stats;
	}
}
