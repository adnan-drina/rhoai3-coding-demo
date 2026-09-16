// JavaStructure: the declarations a decided repair edits, from the JDK
// compiler's own parse tree (never from text matching).
//
// The bootstrap runs before the destination has ever been built, so there is
// no classpath and full attribution would mark every framework annotation
// unresolved. What a decided repair needs is structural and is
// fully answered by the parse tree plus the Java Language Specification's
// import rules, which the caller applies: every import (single-type,
// on-demand, static), every type declaration with its nesting, every member
// with its annotations, and for each annotation the exact source range of the
// annotation and of each argument, with a string literal's DECODED value.
// Positions are character offsets into the file as javac read it (UTF-16 code
// units); the caller cuts in the same units.
//
// A file that does not parse is reported with its errors and no structure:
// the caller must refuse rather than edit it.
//
//   java JavaStructure --root <dir> --out <json> [--files <list>] [<relative path>...]
import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import javax.lang.model.element.Modifier;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

import com.sun.source.tree.AnnotationTree;
import com.sun.source.tree.AssignmentTree;
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ExpressionTree;
import com.sun.source.tree.IdentifierTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.LiteralTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.ModifiersTree;
import com.sun.source.tree.Tree;
import com.sun.source.tree.VariableTree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.Trees;

public final class JavaStructure {

    public static void main(String[] args) throws IOException {
        Path root = null, out = null;
        List<String> rels = new ArrayList<>();
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--root": root = Paths.get(args[++i]); break;
                case "--out": out = Paths.get(args[++i]); break;
                // a file listing one relative path per line (no argv length limit)
                case "--files":
                    for (String line : Files.readAllLines(Paths.get(args[++i]), StandardCharsets.UTF_8)) {
                        if (!line.isBlank()) { rels.add(line.strip()); }
                    }
                    break;
                default: rels.add(args[i]);
            }
        }
        if (root == null || out == null) {
            System.err.println("usage: JavaStructure --root <dir> --out <json> <relative path>...");
            System.exit(2);
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) { System.err.println("no system java compiler (a JDK, not a JRE)"); System.exit(1); }
        List<Object> files = new ArrayList<>();
        try (StandardJavaFileManager fm = compiler.getStandardFileManager(null, null, StandardCharsets.UTF_8)) {
            for (String rel : rels) {
                files.add(describe(compiler, fm, root, rel));
            }
        }
        Map<String, Object> doc = new LinkedHashMap<>();
        doc.put("schema", "rhoai3.java-structure/v1");
        doc.put("files", files);
        try (Writer w = Files.newBufferedWriter(out, StandardCharsets.UTF_8)) {
            Json.write(w, doc);
        }
    }

    static Map<String, Object> describe(JavaCompiler compiler, StandardJavaFileManager fm, Path root, String rel) throws IOException {
        Map<String, Object> f = new LinkedHashMap<>();
        f.put("path", rel);
        Path file = root.resolve(rel);
        if (!Files.isRegularFile(file)) {
            f.put("exists", false);
            return f;
        }
        f.put("exists", true);
        String src = Files.readString(file, StandardCharsets.UTF_8);
        DiagnosticCollector<JavaFileObject> diags = new DiagnosticCollector<>();
        JavacTask task = (JavacTask) compiler.getTask(null, fm, diags, List.of("-proc:none"), null,
                fm.getJavaFileObjectsFromPaths(List.of(file)));
        Iterable<? extends CompilationUnitTree> units = task.parse();
        List<Object> errors = new ArrayList<>();
        for (Diagnostic<? extends JavaFileObject> d : diags.getDiagnostics()) {
            if (d.getKind() == Diagnostic.Kind.ERROR) {
                Map<String, Object> e = new LinkedHashMap<>();
                e.put("line", d.getLineNumber());
                e.put("code", d.getCode());
                e.put("message", d.getMessage(null));
                errors.add(e);
            }
        }
        f.put("parse_errors", errors);
        if (!errors.isEmpty()) {
            return f;
        }
        Trees trees = Trees.instance(task);
        SourcePositions pos = trees.getSourcePositions();
        for (CompilationUnitTree cu : units) {
            String pkg = cu.getPackageName() == null ? "" : cu.getPackageName().toString();
            f.put("package", pkg);
            f.put("package_end", cu.getPackage() == null ? -1L : pos.getEndPosition(cu, cu.getPackage()));
            List<Object> imports = new ArrayList<>();
            for (ImportTree imp : cu.getImports()) {
                Map<String, Object> m = new LinkedHashMap<>();
                String name = imp.getQualifiedIdentifier().toString();
                boolean onDemand = name.endsWith(".*");
                m.put("name", onDemand ? name.substring(0, name.length() - 2) : name);
                m.put("static", imp.isStatic());
                m.put("on_demand", onDemand);
                m.put("start", pos.getStartPosition(cu, imp));
                m.put("end", pos.getEndPosition(cu, imp));
                imports.add(m);
            }
            f.put("imports", imports);
            List<Object> types = new ArrayList<>();
            for (Tree t : cu.getTypeDecls()) {
                if (t instanceof ClassTree) {
                    collectType(cu, pos, src, (ClassTree) t, pkg.isEmpty() ? "" : pkg + ".", types);
                }
            }
            f.put("types", types);
        }
        return f;
    }

    static void collectType(CompilationUnitTree cu, SourcePositions pos, String src, ClassTree ct, String prefix, List<Object> types) {
        Map<String, Object> t = new LinkedHashMap<>();
        String fqn = prefix + ct.getSimpleName();
        t.put("fqn", fqn);
        t.put("simple", ct.getSimpleName().toString());
        t.put("kind", ct.getKind().toString().toLowerCase());
        t.put("start", pos.getStartPosition(cu, ct));
        t.put("end", pos.getEndPosition(cu, ct));
        modifiers(cu, pos, src, ct.getModifiers(), t);
        List<Object> members = new ArrayList<>();
        List<ClassTree> nested = new ArrayList<>();
        for (Tree m : ct.getMembers()) {
            Map<String, Object> row = new LinkedHashMap<>();
            if (m instanceof VariableTree) {
                VariableTree v = (VariableTree) m;
                row.put("kind", "field");
                row.put("name", v.getName().toString());
                row.put("type", source(cu, pos, src, v.getType()));
                row.put("start", pos.getStartPosition(cu, v));
                modifiers(cu, pos, src, v.getModifiers(), row);
            } else if (m instanceof MethodTree) {
                MethodTree mt = (MethodTree) m;
                String name = mt.getName().toString();
                row.put("kind", "<init>".equals(name) ? "constructor" : "method");
                row.put("name", name);
                List<Object> params = new ArrayList<>();
                for (VariableTree p : mt.getParameters()) {
                    params.add(source(cu, pos, src, p.getType()));
                }
                row.put("params", params);
                row.put("start", pos.getStartPosition(cu, mt));
                modifiers(cu, pos, src, mt.getModifiers(), row);
            } else if (m instanceof ClassTree) {
                nested.add((ClassTree) m);
                continue;
            } else {
                continue;
            }
            members.add(row);
        }
        t.put("members", members);
        types.add(t);
        for (ClassTree n : nested) {
            collectType(cu, pos, src, n, fqn + ".", types);
        }
    }

    static void modifiers(CompilationUnitTree cu, SourcePositions pos, String src, ModifiersTree mods, Map<String, Object> into) {
        long start = pos.getStartPosition(cu, mods);
        into.put("modifiers_start", start);
        List<String> flags = new ArrayList<>();
        for (Modifier mod : mods.getFlags()) {
            flags.add(mod.toString());
        }
        into.put("modifiers", flags);
        List<Object> anns = new ArrayList<>();
        for (AnnotationTree a : mods.getAnnotations()) {
            anns.add(annotation(cu, pos, src, a));
        }
        into.put("annotations", anns);
    }

    static Map<String, Object> annotation(CompilationUnitTree cu, SourcePositions pos, String src, AnnotationTree a) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("name", typeName(a.getAnnotationType()));
        long start = pos.getStartPosition(cu, a), end = pos.getEndPosition(cu, a);
        m.put("start", start);
        m.put("end", end);
        m.put("source", slice(src, start, end));
        List<Object> args = new ArrayList<>();
        for (ExpressionTree arg : a.getArguments()) {
            Map<String, Object> row = new LinkedHashMap<>();
            ExpressionTree value = arg;
            String name = "value";
            // `@A(x)` is the single-element shorthand for `@A(value = x)`; javac
            // may represent either form as an assignment.
            if (arg instanceof AssignmentTree) {
                AssignmentTree as = (AssignmentTree) arg;
                name = as.getVariable().toString();
                value = as.getExpression();
                row.put("explicit_name", true);
            } else {
                row.put("explicit_name", false);
            }
            row.put("name", name);
            long vs = pos.getStartPosition(cu, value), ve = pos.getEndPosition(cu, value);
            row.put("start", vs);
            row.put("end", ve);
            row.put("source", slice(src, vs, ve));
            if (value instanceof LiteralTree && value.getKind() == Tree.Kind.STRING_LITERAL) {
                row.put("kind", "string_literal");
                row.put("value", String.valueOf(((LiteralTree) value).getValue()));
            } else {
                row.put("kind", "other");
            }
            args.add(row);
        }
        m.put("args", args);
        return m;
    }

    static String typeName(Tree t) {
        if (t instanceof IdentifierTree) {
            return ((IdentifierTree) t).getName().toString();
        }
        if (t instanceof MemberSelectTree) {
            MemberSelectTree ms = (MemberSelectTree) t;
            return typeName(ms.getExpression()) + "." + ms.getIdentifier();
        }
        return t.toString();
    }

    static String source(CompilationUnitTree cu, SourcePositions pos, String src, Tree t) {
        if (t == null) { return ""; }
        long s = pos.getStartPosition(cu, t), e = pos.getEndPosition(cu, t);
        return slice(src, s, e);
    }

    static String slice(String src, long s, long e) {
        if (s < 0 || e < 0 || e > src.length() || s > e) { return ""; }
        return src.substring((int) s, (int) e);
    }

    /** Minimal JSON writer: maps, lists, strings, numbers, booleans, null. */
    static final class Json {
        static void write(Writer w, Object o) throws IOException {
            if (o == null) { w.write("null"); return; }
            if (o instanceof String) { str(w, (String) o); return; }
            if (o instanceof Number || o instanceof Boolean) { w.write(o.toString()); return; }
            if (o instanceof Map) {
                w.write('{');
                boolean first = true;
                for (Map.Entry<?, ?> e : ((Map<?, ?>) o).entrySet()) {
                    if (!first) { w.write(','); }
                    first = false;
                    str(w, String.valueOf(e.getKey()));
                    w.write(':');
                    write(w, e.getValue());
                }
                w.write('}');
                return;
            }
            if (o instanceof List) {
                w.write('[');
                boolean first = true;
                for (Object x : (List<?>) o) {
                    if (!first) { w.write(','); }
                    first = false;
                    write(w, x);
                }
                w.write(']');
                return;
            }
            str(w, o.toString());
        }

        static void str(Writer w, String s) throws IOException {
            w.write('"');
            for (int i = 0; i < s.length(); i++) {
                char c = s.charAt(i);
                switch (c) {
                    case '"': w.write("\\\""); break;
                    case '\\': w.write("\\\\"); break;
                    case '\n': w.write("\\n"); break;
                    case '\r': w.write("\\r"); break;
                    case '\t': w.write("\\t"); break;
                    default:
                        if (c < 0x20 || c > 0x7e) {
                            w.write(String.format("\\u%04x", (int) c));
                        } else {
                            w.write(c);
                        }
                }
            }
            w.write('"');
        }
    }
}
