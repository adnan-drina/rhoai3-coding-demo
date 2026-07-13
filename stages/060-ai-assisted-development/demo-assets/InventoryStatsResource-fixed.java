package com.redhat.coolstore.inventory;

import java.util.HashMap;
import java.util.Map;

import org.jboss.logging.Logger;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

@Path("/api/inventory/stats")
@Produces(MediaType.APPLICATION_JSON)
@ApplicationScoped
public class InventoryStatsResource {

	private static final Logger LOG = Logger.getLogger(InventoryStatsResource.class);

	private final InventoryRepository repository;

	@Inject
	public InventoryStatsResource(InventoryRepository repository) {
		this.repository = repository;
	}

	@GET
	public Map<String, Object> getStats() {
		Map<String, Object> stats = new HashMap<>();

		LOG.info("Fetching inventory statistics");

		try {
			var items = repository.list();
			stats.put("total", items.size());

			Map<String, Long> byLocation = new HashMap<>();
			for (var item : items) {
				byLocation.merge(item.location(), 1L, Long::sum);
			}
			stats.put("by_location", byLocation);

			long inStock = items.stream().filter(i -> i.quantity() > 0).count();
			stats.put("in_stock", inStock);
			stats.put("out_of_stock", items.size() - inStock);
		} catch (Exception e) {
			LOG.error("Failed to compute inventory statistics", e);
		}

		return stats;
	}
}
