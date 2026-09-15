#!/usr/bin/env python3
"""Policy test: introduce a change that violates the rest->repository crossing,
and a passing counterpart that does the same work through the service facade.

  python3 mutate.py violating   # controller reaches the repository directly
  python3 mutate.py passing     # same feature, through the service facade
  python3 mutate.py remove      # restore
"""
import pathlib, sys

P = pathlib.Path("/Users/adrina/Sandbox/rgctl-experiment/app/src/main/java/"
                 "org/springframework/samples/petclinic/rest/VetRestController.java")
ANCHOR = "public class VetRestController {\n"

VIOLATING = """
    // POLICY TEST (temporary): a controller reaching the repository layer directly,
    // bypassing the service facade. Removed after the check runs.
    @jakarta.inject.Inject
    org.springframework.samples.petclinic.repository.VetRepository policyTestRepository;

    @org.springframework.web.bind.annotation.RequestMapping(
        value = "/policy-test-count", method = org.springframework.web.bind.annotation.RequestMethod.GET)
    public org.springframework.http.ResponseEntity<Integer> policyTestCount() {
        return new org.springframework.http.ResponseEntity<>(
            this.policyTestRepository.findAll().size(), org.springframework.http.HttpStatus.OK);
    }
"""

PASSING = """
    // POLICY TEST (temporary): the same feature, reaching the same data through the
    // service facade the source declares. Removed after the check runs.
    @org.springframework.web.bind.annotation.RequestMapping(
        value = "/policy-test-count", method = org.springframework.web.bind.annotation.RequestMethod.GET)
    public org.springframework.http.ResponseEntity<Integer> policyTestCount() {
        return new org.springframework.http.ResponseEntity<>(
            this.clinicService.findAllVets().size(), org.springframework.http.HttpStatus.OK);
    }
"""

mode = sys.argv[1]
t = P.read_text()
for block in (VIOLATING, PASSING):
    t = t.replace(block, "")
if mode == "violating":
    t = t.replace(ANCHOR, ANCHOR + VIOLATING, 1)
elif mode == "passing":
    t = t.replace(ANCHOR, ANCHOR + PASSING, 1)
elif mode != "remove":
    raise SystemExit("usage: mutate.py violating|passing|remove")
P.write_text(t)
print(mode, "applied to", P.name)
