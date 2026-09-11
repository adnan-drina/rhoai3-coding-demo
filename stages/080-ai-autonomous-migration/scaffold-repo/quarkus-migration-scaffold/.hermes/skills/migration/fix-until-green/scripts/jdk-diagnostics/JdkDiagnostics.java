import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

/**
 * Compile the destination sources with the JDK compiler API and emit every
 * diagnostic as JSON (rhoai3.diagnostics/v1). The work list turns ERROR
 * diagnostics into items; nothing is parsed from Maven log text.
 *
 * Usage: java JdkDiagnostics --source DIR --out FILE [--classpath FILE] [--release N] [--tests]
 */
public final class JdkDiagnostics {
    public static void main(String[] args) throws IOException {
        String source = null, out = null, classpath = null, release = "21";
        boolean tests = false;
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--source": source = args[++i]; break;
                case "--out": out = args[++i]; break;
                case "--classpath": classpath = args[++i]; break;
                case "--release": release = args[++i]; break;
                case "--tests": tests = true; break;
                default: System.err.println("unknown arg " + args[i]); System.exit(2);
            }
        }
        if (source == null || out == null) { System.err.println("usage: JdkDiagnostics --source DIR --out FILE [--classpath FILE] [--release N] [--tests]"); System.exit(2); }
        Path root = Paths.get(source).toAbsolutePath().normalize();
        List<Path> files = new ArrayList<>();
        List<String> roots = new ArrayList<>();
        roots.add("src/main/java");
        if (tests) roots.add("src/test/java");
        // Generated sources are part of the build (build-helper add-source,
        // annotation processors): a diagnostic there is a real error of the
        // build, owned by the generator's configuration in the pom. Without
        // them every reference to a generated type is a phantom error
        // (pilot v6: 132 of 829 named the OpenAPI DTOs that existed on disk).
        Path gen = root.resolve("target/generated-sources");
        if (Files.isDirectory(gen)) {
            try (Stream<Path> s = Files.list(gen)) {
                s.filter(Files::isDirectory).sorted().forEach(d -> roots.add(root.relativize(d).toString()));
            }
        }
        for (String r : roots) {
            Path p = root.resolve(r);
            if (!Files.isDirectory(p)) continue;
            try (Stream<Path> s = Files.walk(p)) {
                s.filter(f -> f.toString().endsWith(".java") && Files.isRegularFile(f)).forEach(files::add);
            }
        }
        files.sort(null);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        DiagnosticCollector<JavaFileObject> collector = new DiagnosticCollector<>();
        StandardJavaFileManager fm = compiler.getStandardFileManager(collector, null, StandardCharsets.UTF_8);
        List<String> options = new ArrayList<>();
        options.add("-proc:none");
        options.add("-Xlint:none");
        options.add("-Xmaxerrs"); options.add("10000");
        // 10,000 is already far above this specimen. javac still reports one
        // unhandled URISyntaxException at a time across sibling files; raising
        // the limit does not complete diagnostic coverage (v8, 2026-09-11).
        options.add("--release"); options.add(release);
        Path scratch = Files.createTempDirectory("jdk-diagnostics");
        options.add("-d"); options.add(scratch.toString());
        List<String> cpEntries = new ArrayList<>();
        if (classpath != null && Files.isRegularFile(Paths.get(classpath))) {
            for (String e : new String(Files.readAllBytes(Paths.get(classpath)), StandardCharsets.UTF_8).trim().split(java.io.File.pathSeparator)) {
                if (!e.isEmpty()) cpEntries.add(e);
            }
        }
        Path classes = root.resolve("target/classes");
        if (Files.isDirectory(classes)) cpEntries.add(classes.toString());
        if (!cpEntries.isEmpty()) { options.add("-classpath"); options.add(String.join(java.io.File.pathSeparator, cpEntries)); }
        boolean ok = true;
        if (!files.isEmpty()) {
            JavaCompiler.CompilationTask task = compiler.getTask(null, fm, collector, options, null, fm.getJavaFileObjectsFromPaths(files));
            ok = Boolean.TRUE.equals(task.call());
        }
        StringBuilder sb = new StringBuilder();
        sb.append("{\"schema\":\"rhoai3.diagnostics/v1\",\"files\":").append(files.size())
          .append(",\"classpath_entries\":").append(cpEntries.size())
          .append(",\"success\":").append(ok).append(",\"diagnostics\":[");
        boolean first = true;
        int errors = 0;
        for (Diagnostic<? extends JavaFileObject> d : collector.getDiagnostics()) {
            String path = "";
            if (d.getSource() != null) {
                Path p = Paths.get(d.getSource().toUri()).toAbsolutePath().normalize();
                try { path = root.relativize(p).toString().replace('\\', '/'); } catch (IllegalArgumentException ex) { path = p.toString(); }
            }
            if (d.getKind() == Diagnostic.Kind.ERROR) errors++;
            if (!first) sb.append(",");
            first = false;
            sb.append("{\"kind\":\"").append(d.getKind()).append("\",\"path\":").append(json(path))
              .append(",\"line\":").append(d.getLineNumber() < 0 ? 0 : d.getLineNumber())
              .append(",\"code\":").append(json(d.getCode() == null ? "" : d.getCode()))
              .append(",\"message\":").append(json(d.getMessage(null))).append("}");
        }
        sb.append("],\"errors\":").append(errors).append("}\n");
        try (Writer w = Files.newBufferedWriter(Paths.get(out), StandardCharsets.UTF_8)) { w.write(sb.toString()); }
        System.err.println("OK: jdk-diagnostics files=" + files.size() + " errors=" + errors);
    }

    static String json(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default: if (c < 0x20 || c > 0x7e) b.append(String.format("\\u%04x", (int) c)); else b.append(c);
            }
        }
        return b.append('"').toString();
    }
}
