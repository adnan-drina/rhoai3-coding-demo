import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.Trees;

import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

/**
 * Documented package renames applied to import declarations, by the JDK
 * compiler's own parse tree (never text matching): every ImportTree whose
 * qualified name is one of the renamed packages, or a member of one, is
 * rewritten at its source position. Nothing else in the file changes.
 *
 * Usage: java JakartaImports --root DIR [--roots src/main/java,...] old.pkg=new.pkg ...
 * Output: one line per rewritten import: path TAB old TAB new (files rewritten in place).
 */
public final class JakartaImports {
    public static void main(String[] args) throws IOException {
        String root = null;
        List<String> roots = new ArrayList<>(List.of("src/main/java"));
        Map<String, String> renames = new LinkedHashMap<>();
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--root": root = args[++i]; break;
                case "--roots": roots = List.of(args[++i].split(",")); break;
                default: {
                    int eq = args[i].indexOf('=');
                    if (eq <= 0) { System.err.println("bad rename " + args[i]); System.exit(2); }
                    renames.put(args[i].substring(0, eq), args[i].substring(eq + 1));
                }
            }
        }
        if (root == null || renames.isEmpty()) { System.err.println("usage: JakartaImports --root DIR old=new ..."); System.exit(2); }
        Path base = Paths.get(root).toAbsolutePath().normalize();
        List<Path> files = new ArrayList<>();
        for (String r : roots) {
            Path p = base.resolve(r);
            if (!Files.isDirectory(p)) continue;
            try (Stream<Path> s = Files.walk(p)) {
                s.filter(f -> f.toString().endsWith(".java") && Files.isRegularFile(f)).forEach(files::add);
            }
        }
        files.sort(null);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        try (StandardJavaFileManager fm = compiler.getStandardFileManager(null, null, StandardCharsets.UTF_8)) {
            for (Path file : files) {
                String src = Files.readString(file, StandardCharsets.UTF_8);
                Iterable<? extends JavaFileObject> units = fm.getJavaFileObjectsFromPaths(List.of(file));
                JavacTask task = (JavacTask) compiler.getTask(null, fm, d -> { }, List.of("-proc:none"), null, units);
                Iterable<? extends CompilationUnitTree> parsed = task.parse();
                Trees trees = Trees.instance(task);
                SourcePositions pos = trees.getSourcePositions();
                // collect edits (start, end, replacement) then apply back-to-front
                List<long[]> spans = new ArrayList<>();
                List<String> texts = new ArrayList<>();
                for (CompilationUnitTree cu : parsed) {
                    for (ImportTree imp : cu.getImports()) {
                        Tree q = imp.getQualifiedIdentifier();
                        long start = pos.getStartPosition(cu, q), end = pos.getEndPosition(cu, q);
                        if (start < 0 || end < 0) continue;
                        String name = src.substring((int) start, (int) end);
                        for (Map.Entry<String, String> e : renames.entrySet()) {
                            String old = e.getKey();
                            if (name.equals(old) || name.startsWith(old + ".")) {
                                String repl = e.getValue() + name.substring(old.length());
                                spans.add(new long[]{start, end});
                                texts.add(repl);
                                System.out.println(base.relativize(file) + "\t" + name + "\t" + repl);
                                break;
                            }
                        }
                    }
                }
                if (spans.isEmpty()) continue;
                StringBuilder sb = new StringBuilder(src);
                for (int i = spans.size() - 1; i >= 0; i--) {
                    sb.replace((int) spans.get(i)[0], (int) spans.get(i)[1], texts.get(i));
                }
                Files.writeString(file, sb.toString(), StandardCharsets.UTF_8);
            }
        }
    }
}
