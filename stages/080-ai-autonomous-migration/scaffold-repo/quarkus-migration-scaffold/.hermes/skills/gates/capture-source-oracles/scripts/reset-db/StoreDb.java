import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;

/**
 * The frozen SOURCE's database, observed where it lives (ADR-020).
 *
 * A refused write's effect on the source can only be read from the state the
 * source itself was left in. The capture therefore runs the source against a
 * database of the SAME engine held in a separate server process, and this
 * runner is the harness's JDBC hand on it:
 *
 *   apply  URL USER PASSWORD FILE...   run each file's statements, in order
 *   script URL USER PASSWORD PATH      write the engine's own full snapshot (SCRIPT) to PATH
 *   revert URL USER PASSWORD PLAN      the fixture revert, checked, all or nothing
 *   observe URL USER PASSWORD TABLES OUT  every row of each table (one bare name per line in TABLES),
 *                                      all columns, written to OUT as sorted "table, column=value..." lines
 *   ping   URL USER PASSWORD           connect and disconnect
 *
 * PLAN is one row per line, tab-separated: table, column, variant value,
 * baseline value, where column, where value, selected rows, table rows. The
 * values are SQL literals and the names bare identifiers, both validated by
 * the harness before they get here. The revert first proves it finds the
 * variant state (the table's baseline row count, the predicate's baseline
 * rows, each holding the variant value), updates exactly those rows, and
 * proves they hold the baseline value; anything else rolls back and exits 3
 * with REVERT_UNEXPECTED_STATE. Credentials arrive as arguments; nothing is
 * printed but counts and names.
 */
public final class StoreDb {

    private StoreDb() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 4) {
            System.err.println("usage: StoreDb apply|script|revert|ping <jdbc-url> <user> <password> [args...]");
            System.exit(2);
        }
        Properties props = new Properties();
        props.setProperty("user", args[2]);
        props.setProperty("password", args[3]);
        try (Connection conn = DriverManager.getConnection(args[1], props)) {
            switch (args[0]) {
                case "ping":
                    System.out.println("connected");
                    break;
                case "apply":
                    for (int i = 4; i < args.length; i++) {
                        int n = 0;
                        for (String sql : split(Files.readString(Path.of(args[i]), StandardCharsets.UTF_8))) {
                            try (Statement st = conn.createStatement()) {
                                st.execute(sql);
                            }
                            n++;
                        }
                        System.out.println("applied " + Path.of(args[i]).getFileName() + " (" + n + " statements)");
                    }
                    break;
                case "script":
                    try (Statement st = conn.createStatement()) {
                        st.execute("SCRIPT '" + args[4].replace("'", "''") + "'");
                    }
                    System.out.println("snapshot written");
                    break;
                case "observe":
                    System.out.println("observed " + observe(conn, Files.readAllLines(Path.of(args[4]), StandardCharsets.UTF_8),
                                                             Path.of(args[5])) + " row(s)");
                    break;
                case "revert":
                    System.exit(revert(conn, Files.readAllLines(Path.of(args[4]), StandardCharsets.UTF_8)));
                    break;
                default:
                    System.err.println("unknown command " + args[0]);
                    System.exit(2);
            }
        }
    }

    private static long count(Statement st, String sql) throws Exception {
        try (ResultSet rs = st.executeQuery(sql)) {
            rs.next();
            return rs.getLong(1);
        }
    }

    private static int revert(Connection conn, List<String> lines) throws Exception {
        conn.setAutoCommit(false);
        try (Statement st = conn.createStatement()) {
            int done = 0;
            for (String line : lines) {
                if (line.isBlank()) {
                    continue;
                }
                String[] f = line.split("\t", -1);
                if (f.length != 8) {
                    conn.rollback();
                    System.err.println("REVERT_PLAN_MALFORMED a plan row has " + f.length + " fields");
                    return 2;
                }
                String t = f[0], c = f[1], variant = f[2], baseline = f[3], k = f[4], w = f[5];
                long rows = Long.parseLong(f[6]), tableRows = Long.parseLong(f[7]);
                String where = k + " = " + w;
                String label = t + "." + c + " where " + where;
                long[] got = {
                    count(st, "SELECT COUNT(*) FROM " + t),
                    count(st, "SELECT COUNT(*) FROM " + t + " WHERE " + where),
                    count(st, "SELECT COUNT(*) FROM " + t + " WHERE " + where + " AND " + c + " IS NOT DISTINCT FROM " + variant),
                };
                long[] want = {tableRows, rows, rows};
                String[] what = {"the table no longer holds the baseline's row count",
                                 "the predicate does not select the baseline's rows",
                                 "the rows do not hold the variant value " + variant};
                for (int i = 0; i < got.length; i++) {
                    if (got[i] != want[i]) {
                        conn.rollback();
                        System.err.println("REVERT_UNEXPECTED_STATE " + label + ": " + what[i] + " (found " + got[i]
                                           + ", expected " + want[i] + ")");
                        return 3;
                    }
                }
                long updated = st.executeUpdate("UPDATE " + t + " SET " + c + " = " + baseline + " WHERE " + where);
                long after = count(st, "SELECT COUNT(*) FROM " + t + " WHERE " + where + " AND " + c + " IS NOT DISTINCT FROM " + baseline);
                if (updated != rows || after != rows) {
                    conn.rollback();
                    System.err.println("REVERT_UNEXPECTED_STATE " + label + ": updated " + updated + " and " + after
                                       + " hold the baseline value " + baseline + ", expected " + rows);
                    return 3;
                }
                done++;
            }
            conn.commit();
            System.out.println("reverted " + done + " row group(s)");
            return 0;
        }
    }

    private static String cell(String v) {
        if (v == null) {
            return "\\N";
        }
        return v.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r");
    }

    /**
     * A consistent read of every row of every scoped table: one transaction at
     * SERIALIZABLE isolation, so the rows are one state, not a moving one.
     */
    private static int observe(Connection conn, List<String> tables, Path out) throws Exception {
        conn.setAutoCommit(false);
        conn.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
        List<String> lines = new ArrayList<>();
        try (Statement st = conn.createStatement()) {
            for (String raw : tables) {
                String t = raw.trim();
                if (t.isEmpty()) {
                    continue;
                }
                if (!t.matches("[A-Za-z_][A-Za-z0-9_$.]*")) {
                    throw new IllegalArgumentException("not a bare table name: " + t);
                }
                try (ResultSet rs = st.executeQuery("SELECT * FROM " + t)) {
                    java.sql.ResultSetMetaData md = rs.getMetaData();
                    int n = md.getColumnCount();
                    while (rs.next()) {
                        StringBuilder b = new StringBuilder(t.toLowerCase());
                        for (int i = 1; i <= n; i++) {
                            b.append('\t').append(md.getColumnLabel(i).toLowerCase()).append('=').append(cell(rs.getString(i)));
                        }
                        lines.add(b.toString());
                    }
                }
                lines.add(t.toLowerCase() + "\t#table");
            }
        }
        conn.commit();
        java.util.Collections.sort(lines);
        Files.writeString(out, String.join("\n", lines) + "\n", StandardCharsets.UTF_8);
        return (int) lines.stream().filter(l -> !l.endsWith("\t#table")).count();
    }

    /** Statements split on the semicolons outside literals; -- comments dropped. */
    static List<String> split(String text) {
        List<String> out = new ArrayList<>();
        StringBuilder buf = new StringBuilder();
        int n = text.length();
        for (int i = 0; i < n; i++) {
            char ch = text.charAt(i);
            if (ch == '\'' || ch == '"') {
                int j = i + 1;
                while (j < n) {
                    if (text.charAt(j) == ch) {
                        if (j + 1 < n && text.charAt(j + 1) == ch) {
                            j += 2;
                            continue;
                        }
                        break;
                    }
                    j++;
                }
                buf.append(text, i, Math.min(j + 1, n));
                i = j;
                continue;
            }
            if (ch == '-' && i + 1 < n && text.charAt(i + 1) == '-') {
                int e = text.indexOf('\n', i);
                i = e < 0 ? n : e;
                buf.append(' ');
                continue;
            }
            if (ch == ';') {
                if (!buf.toString().isBlank()) {
                    out.add(buf.toString().trim());
                }
                buf.setLength(0);
                continue;
            }
            buf.append(ch);
        }
        if (!buf.toString().isBlank()) {
            out.add(buf.toString().trim());
        }
        return out;
    }
}
