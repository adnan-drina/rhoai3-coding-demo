package com.redhat.coolstore.inventory;

import java.util.HashMap;
import java.util.Map;

import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

@Path("/api/inventory/stats")
@Produces(MediaType.APPLICATION_JSON)
public class InventoryStatsResource {

	@Inject
	InventoryRepository repository;

	@GET
	public Map<String, Object> getStats() {
		Map<String, Object> stats = new HashMap<>();

		System.out.println("Fetching inventory statistics");

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
		}

		return stats;
	}
}
