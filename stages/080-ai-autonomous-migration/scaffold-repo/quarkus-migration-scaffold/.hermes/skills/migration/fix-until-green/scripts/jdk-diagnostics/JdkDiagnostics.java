import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.stream.Stream;

import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

import com.sun.source.tree.CatchTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.TaskEvent;
import com.sun.source.util.TaskListener;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;

/**
 * Compile the destination sources with the JDK compiler API and emit every
 * diagnostic as JSON (rhoai3.diagnostics/v1). The work list turns ERROR
 * diagnostics into items; nothing is parsed from Maven log text.
 *
 * Usage: java JdkDiagnostics --source DIR --out FILE [--classpath FILE] [--release N] [--tests]
 *        [--exclude-output-classes]
 *
 * Identity: ``message`` is rendered in the ROOT locale (javac's base,
 * English, bundle) whatever the JVM's default locale is, so the same source
 * yields the same text on every workstation; the JVM-locale rendering is kept
 * beside it as ``message_jvm_locale`` for investigation, only when it differs.
 * ``column`` and, when the JVM exposes them, the compiler's structured
 * ``args`` (symbol kinds and names, never prose) keep two diagnostics at one
 * line distinguishable; plan semantics v1 derives obligation identity from
 * those, not from localized text.
 *
 * Provenance: ``generated_roots`` records each registered generated-source
 * root with its file count and content digest, and
 * ``output_classes_on_classpath`` whether target/classes was on the classpath.
 * --exclude-output-classes leaves it off: an orphan class from an earlier
 * build resolves a reference whose source is gone and hides a real error, so
 * the controlled initial analysis never reads it.
 *
 * Site (v30 H-3): ``site`` names the syntactic position of an error as the
 * compiler's own tree states it -- ``import``, ``throws`` (a method's throws
 * clause), ``catch`` (a catch parameter's type) or ``other`` -- so a brief can
 * separate mechanical removals from decision sites without reading message
 * text. Presentation evidence only: it is not part of an obligation's identity.
 */
public final class JdkDiagnostics {
    public static void main(String[] args) throws IOException {
        String source = null, out = null, classpath = null, release = "21";
        boolean tests = false;
        boolean excludeOutputClasses = false;
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--source": source = args[++i]; break;
                case "--out": out = args[++i]; break;
                case "--classpath": classpath = args[++i]; break;
                case "--release": release = args[++i]; break;
                case "--tests": tests = true; break;
                case "--exclude-output-classes": excludeOutputClasses = true; break;
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
        List<String> genRoots = new ArrayList<>();
        if (Files.isDirectory(gen)) {
            try (Stream<Path> s = Files.list(gen)) {
                s.filter(Files::isDirectory).sorted().forEach(d -> genRoots.add(root.relativize(d).toString().replace('\\', '/')));
            }
        }
        roots.addAll(genRoots);
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
        boolean outputClasses = !excludeOutputClasses && Files.isDirectory(classes);
        if (outputClasses) cpEntries.add(classes.toString());
        if (!cpEntries.isEmpty()) { options.add("-classpath"); options.add(String.join(java.io.File.pathSeparator, cpEntries)); }
        boolean ok = true;
        java.util.Map<java.net.URI, CompilationUnitTree> units = new java.util.HashMap<>();
        SourcePositions positions = null;
        if (!files.isEmpty()) {
            JavaCompiler.CompilationTask task = compiler.getTask(null, fm, collector, options, null, fm.getJavaFileObjectsFromPaths(files));
            if (task instanceof JavacTask) {
                // observe the parsed units only; the compilation itself is exactly task.call()
                ((JavacTask) task).addTaskListener(new TaskListener() {
                    @Override public void finished(TaskEvent e) {
                        if (e.getKind() == TaskEvent.Kind.PARSE && e.getCompilationUnit() != null) {
                            units.put(e.getSourceFile().toUri(), e.getCompilationUnit());
                        }
                    }
                });
                positions = Trees.instance(task).getSourcePositions();
            }
            ok = Boolean.TRUE.equals(task.call());
        }
        StringBuilder sb = new StringBuilder();
        sb.append("{\"schema\":\"rhoai3.diagnostics/v1\",\"files\":").append(files.size())
          .append(",\"classpath_entries\":").append(cpEntries.size())
          .append(",\"rendering_locale\":\"root\"")
          .append(",\"jvm_locale\":").append(json(Locale.getDefault().toLanguageTag()))
          .append(",\"output_classes_on_classpath\":").append(outputClasses)
          .append(",\"generated_roots\":[");
        for (int g = 0; g < genRoots.size(); g++) {
            if (g > 0) sb.append(",");
            sb.append(rootRecord(root, genRoots.get(g)));
        }
        sb.append("]");
        // all or nothing: identity may not mix structured and textual keys
        boolean argsAvailable = true;
        for (Diagnostic<? extends JavaFileObject> d : collector.getDiagnostics()) {
            if (structuredArgs(d) == null) { argsAvailable = false; break; }
        }
        sb.append(",\"args_available\":").append(argsAvailable)
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
              .append(",\"column\":").append(d.getColumnNumber() < 0 ? 0 : d.getColumnNumber())
              .append(",\"code\":").append(json(d.getCode() == null ? "" : d.getCode()));
            String pinned = d.getMessage(Locale.ROOT);
            String local = d.getMessage(null);
            sb.append(",\"message\":").append(json(pinned));
            if (!pinned.equals(local)) sb.append(",\"message_jvm_locale\":").append(json(local));
            if (d.getSource() != null && positions != null && units.containsKey(d.getSource().toUri())) {
                sb.append(",\"site\":").append(json(site(units.get(d.getSource().toUri()), positions, d.getPosition())));
            }
            List<String> dargs = argsAvailable ? structuredArgs(d) : null;
            if (dargs != null) {
                sb.append(",\"args\":[");
                for (int a = 0; a < dargs.size(); a++) { if (a > 0) sb.append(","); sb.append(json(dargs.get(a))); }
                sb.append("]");
            }
            sb.append("}");
        }
        sb.append("],\"errors\":").append(errors).append("}\n");
        try (Writer w = Files.newBufferedWriter(Paths.get(out), StandardCharsets.UTF_8)) { w.write(sb.toString()); }
        System.err.println("OK: jdk-diagnostics files=" + files.size() + " errors=" + errors);
    }

    /** import | throws | catch | other: the innermost tree at {@code pos}, read upward. */
    static String site(CompilationUnitTree cu, SourcePositions sp, long pos) {
        if (pos < 0) return "other";
        final TreePath[] best = {null};
        new TreePathScanner<Void, Void>() {
            @Override public Void scan(Tree t, Void v) {
                if (t == null) return null;
                long s = sp.getStartPosition(cu, t), e = sp.getEndPosition(cu, t);
                if (s >= 0 && e >= 0 && (pos < s || pos >= e)) return null;
                if (s >= 0 && e >= 0) best[0] = new TreePath(getCurrentPath() == null ? new TreePath(cu) : getCurrentPath(), t);
                return super.scan(t, v);
            }
        }.scan(cu, null);
        for (TreePath p = best[0]; p != null && p.getParentPath() != null; p = p.getParentPath()) {
            Tree leaf = p.getLeaf(), up = p.getParentPath().getLeaf();
            if (leaf instanceof ImportTree) return "import";
            if (up instanceof MethodTree && ((MethodTree) up).getThrows().contains(leaf)) return "throws";
            if (up instanceof CatchTree && ((CatchTree) up).getParameter() == leaf) return "catch";
            if (leaf instanceof ImportTree || leaf instanceof MethodTree) break;
        }
        if (best[0] != null && best[0].getLeaf() instanceof ImportTree) return "import";
        return "other";
    }

    /** A generated root: its file count and a digest over (relative path, bytes). */
    static String rootRecord(Path root, String rel) throws IOException {
        List<Path> fs = new ArrayList<>();
        try (Stream<Path> s = Files.walk(root.resolve(rel))) {
            s.filter(Files::isRegularFile).forEach(fs::add);
        }
        fs.sort(null);
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            for (Path f : fs) {
                md.update(root.relativize(f).toString().replace('\\', '/').getBytes(StandardCharsets.UTF_8));
                md.update((byte) 0);
                md.update(Files.readAllBytes(f));
                md.update((byte) 0);
            }
            StringBuilder h = new StringBuilder();
            for (byte b : md.digest()) h.append(String.format("%02x", b));
            return "{\"root\":" + json(rel) + ",\"files\":" + fs.size() + ",\"sha256\":\"" + h + "\"}";
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IOException(e);
        }
    }

    /**
     * The compiler's own diagnostic arguments (symbol kinds, names, types), or
     * null when this JVM does not expose them (javac's internals need
     * --add-exports jdk.compiler/com.sun.tools.javac.api and .util). Never
     * localized prose: a kind renders as its key ("kindname.class").
     */
    static List<String> structuredArgs(Diagnostic<?> d) {
        try {
            Object jc = d;
            try {
                java.lang.reflect.Field f = d.getClass().getField("d");
                jc = f.get(d);
            } catch (NoSuchFieldException ignore) {
                // already the compiler's own diagnostic
            }
            java.lang.reflect.Method m = jc.getClass().getMethod("getArgs");
            Object[] raw = (Object[]) m.invoke(jc);
            List<String> out = new ArrayList<>();
            for (Object o : raw) out.add(argText(o));
            return out;
        } catch (ReflectiveOperationException | RuntimeException e) {
            return null;
        }
    }

    static String argText(Object o) throws ReflectiveOperationException {
        if (o == null) return "";
        if (o instanceof Diagnostic) {
            List<String> inner = structuredArgs((Diagnostic<?>) o);
            return ((Diagnostic<?>) o).getCode() + (inner == null ? "" : inner.toString());
        }
        if (o instanceof Enum) {
            try {
                java.lang.reflect.Method k = o.getClass().getMethod("getKey");
                return String.valueOf(k.invoke(o));
            } catch (NoSuchMethodException e) {
                return ((Enum<?>) o).name();
            }
        }
        return String.valueOf(o);
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
