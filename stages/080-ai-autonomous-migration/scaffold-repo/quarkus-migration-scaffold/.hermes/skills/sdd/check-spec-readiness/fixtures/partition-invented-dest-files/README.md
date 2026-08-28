# dest-9 invented dest Java (file twin of invented-routes)

dest-9 M2 `files_writable` named `Application.java` and `GreetingResource.java`.
Type-inventory dest twin is only `Greeting.java`. Invented-routes does not
see that (Operator `3e3409d0`).

```bash
python3 ../../scripts/assert-partition-invented-files.py .
# exit 1, invented_file Application.java and GreetingResource.java
```
