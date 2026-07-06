# Image Source Review Pattern

Use this pattern when reviewing image references:

1. Identify the product owner for each image: OCP, RHOAI, ODF, or demo app.
2. Confirm product images come from official Red Hat sources captured by the
   relevant skill.
3. Check whether the connected demo can pull the image with existing pull
   secrets and trust.
4. If disconnected support is required, define the `oc mirror` image set and
   generated mirror resources as a separate implementation decision.
5. Keep credentials and pull-secret data out of GitOps manifests.
