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
 * INCONCLUSIVE. Credentials arrive as arguments from environment variables the
 * decision references by name; nothing is printed but counts.
 *
 *   java -cp <driver.jar>:. ResetDb <jdbc-url> <user> <password> <sql-file>...
 */
public final class ResetDb {

    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("usage: ResetDb <jdbc-url> <user> <password> [sql-file...]");
            System.exit(2);
        }
        Properties props = new Properties();
        props.setProperty("user", args[1]);
        props.setProperty("password", args[2]);
        try (Connection conn = DriverManager.getConnection(args[0], props)) {
            try (Statement st = conn.createStatement()) {
                st.execute("DROP SCHEMA IF EXISTS public CASCADE");
                st.execute("CREATE SCHEMA public");
            }
            for (int i = 3; i < args.length; i++) {
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
