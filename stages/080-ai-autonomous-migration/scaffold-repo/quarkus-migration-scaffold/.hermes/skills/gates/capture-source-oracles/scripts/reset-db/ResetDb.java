import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.Properties;

/**
 * Restore a database to the initial state a scenario corpus declares: drop and
 * recreate the schema, then apply the schema and seed files the decision names.
 *
 * JDBC rather than a command-line client, because the workspace that runs the
 * parity comparison has a JDK and the destination's own driver on disk but no
 * psql, and a reset that cannot run turns every reset_before scenario
 * INCONCLUSIVE. Arguments name environment variables; credential values stay
 * out of the process command line.
 *
 *   java -cp <driver.jar>:. ResetDb <url-env> <user-env> <password-env> <sql-file>...
 *   java -cp <driver.jar>:. ResetDb <url-env> <user-env> <password-env> --keep-schema <sql-file>...
 *
 * --keep-schema applies the files to the database as it is: a fixture
 * variant's revert changes only the rows it proves it found, and a dropped
 * schema would erase the very state the revert is there to leave readable.
 */
public final class ResetDb {

    private static String requiredEnv(String name) {
        String value = System.getenv(name);
        if (value == null || value.isEmpty()) {
            throw new IllegalArgumentException("required reset environment variable is not set: " + name);
        }
        return value;
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("usage: ResetDb <url-env> <user-env> <password-env> [sql-file...]");
            System.exit(2);
        }
        Properties props = new Properties();
        String url = requiredEnv(args[0]);
        props.setProperty("user", requiredEnv(args[1]));
        props.setProperty("password", requiredEnv(args[2]));
        boolean keep = args.length > 3 && "--keep-schema".equals(args[3]);
        try (Connection conn = DriverManager.getConnection(url, props)) {
            if (!keep) {
                try (Statement st = conn.createStatement()) {
                    st.execute("DROP SCHEMA IF EXISTS public CASCADE");
                    st.execute("CREATE SCHEMA public");
                }
            }
            for (int i = keep ? 4 : 3; i < args.length; i++) {
                Path p = Path.of(args[i]);
                String sql = Files.readString(p, StandardCharsets.UTF_8);
                try (Statement st = conn.createStatement()) {
                    st.execute(sql);
                }
                System.out.println("applied " + p.getFileName());
            }
            try (Statement st = conn.createStatement();
                 ResultSet rs = st.executeQuery(
                     "select count(*) from information_schema.tables where table_schema = 'public'")) {
                rs.next();
                System.out.println("tables in public: " + rs.getInt(1));
            }
        }
    }
}
