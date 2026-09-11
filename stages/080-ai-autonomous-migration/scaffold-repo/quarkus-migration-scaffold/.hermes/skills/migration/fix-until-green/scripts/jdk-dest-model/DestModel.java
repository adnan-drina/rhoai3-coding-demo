// DestModel: the DESTINATION's own structure, from the JDK's compiler API.
//
// The M1 extractor models the frozen SOURCE and is pinned to that job. The
// loop needs the same kind of truth about the tree it is editing right now:
// which members a repository actually declares, which it actually inherits,
// and exactly where each profile condition sits. Regex answered those
// questions wrongly in every direction -- it read a fully qualified
// annotation as absent, a redeclared findAll as underivable, and a deleted
// member as inherited.
//
// Everything here is resolved by javac. A declaration javac could not
// resolve, or an annotation argument that is not a string literal, is
// reported INCONCLUSIVE and never as a pass: the caller must refuse rather
// than guess.
//
//   java DestModel --source <dir> --out <json> --release <n> [--classpath <file>]
import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import javax.lang.model.element.AnnotationMirror;
import javax.lang.model.element.Element;
import javax.lang.model.element.ElementKind;
import javax.lang.model.element.ExecutableElement;
import javax.lang.model.element.TypeElement;
import javax.lang.model.type.TypeMirror;
import javax.lang.model.util.Elements;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

import com.sun.source.tree.AnnotationTree;
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.ExpressionTree;
import com.sun.source.tree.LiteralTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.ModifiersTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;

public final class DestModel {

    public static void main(String[] args) throws Exception {
        Path source = null, out = null, classpath = null;
        String release = "21";
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--source": source = Paths.get(args[++i]); break;
                case "--out": out = Paths.get(args[++i]); break;
                case "--release": release = args[++i]; break;
                case "--classpath": classpath = Paths.get(args[++i]); break;
                default: throw new IllegalArgumentException("unknown argument " + args[i]);
            }
        }
        if (source == null || out == null) {
            System.err.println("usage: DestModel --source <dir> --out <json> [--release <n>] [--classpath <file>]");
            System.exit(2);
        }
        List<Path> files;
        try (Stream<Path> walk = Files.walk(source)) {
            files = walk.filter(p -> p.toString().endsWith(".java")).sorted().collect(Collectors.toList());
        }
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) { System.err.println("no system java compiler (a JDK, not a JRE)"); System.exit(1); }
        DiagnosticCollector<JavaFileObject> diags = new DiagnosticCollector<>();
        StandardJavaFileManager fm = compiler.getStandardFileManager(diags, null, StandardCharsets.UTF_8);
        List<String> options = new ArrayList<>(Arrays.asList("-proc:none", "-nowarn", "--release", release));
        if (classpath != null && Files.isReadable(classpath)) {
            String cp = new String(Files.readAllBytes(classpath), StandardCharsets.UTF_8).trim();
            if (!cp.isEmpty()) { options.add("-classpath"); options.add(cp); }
        }
        JavacTask task = (JavacTask) compiler.getTask(null, fm, diags,
                options, null, fm.getJavaFileObjectsFromPaths(files));
        Iterable<? extends CompilationUnitTree> units = task.parse();
        task.analyze();
        Trees trees = Trees.instance(task);
        Elements elements = task.getElements();
        SourcePositions positions = trees.getSourcePositions();

        // A file javac reported an error in is not a file this model may be
        // trusted about, and saying so is the whole point.
        TreeSet<String> broken = new TreeSet<>();
        for (Diagnostic<? extends JavaFileObject> d : diags.getDiagnostics()) {
            if (d.getKind() == Diagnostic.Kind.ERROR && d.getSource() != null) {
                broken.add(rel(source, Paths.get(d.getSource().toUri())));
            }
        }

        List<Map<String, Object>> types = new ArrayList<>();
        Path root = source;
        for (CompilationUnitTree unit : units) {
            Path file = Paths.get(unit.getSourceFile().toUri());
            String relPath = rel(root, file);
            boolean ok = !broken.contains(relPath);
            // The import list, so a caller can bind a simple annotation name
            // to its type even in a tree that cannot yet be compiled against
            // its dependencies (the bootstrap runs before the first build).
            List<String> imports = new ArrayList<>();
            for (com.sun.source.tree.ImportTree imp : unit.getImports()) {
                imports.add(imp.getQualifiedIdentifier().toString());
            }
            new TreePathScanner<Void, Void>() {
                @Override public Void visitClass(ClassTree node, Void unused) {
                    TreePath path = getCurrentPath();
                    Element el = trees.getElement(path);
                    if (!(el instanceof TypeElement)) { return super.visitClass(node, unused); }
                    TypeElement type = (TypeElement) el;
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("path", relPath);
                    row.put("fqn", type.getQualifiedName().toString());
                    row.put("kind", type.getKind().toString().toLowerCase());
                    row.put("resolution", ok ? "full" : "partial");
                    row.put("imports", imports);
                    List<String> supers = new ArrayList<>();
                    if (type.getSuperclass() != null && type.getSuperclass().getKind().name().equals("DECLARED")) {
                        supers.add(type.getSuperclass().toString());
                    }
                    for (TypeMirror itf : type.getInterfaces()) { supers.add(itf.toString()); }
                    row.put("supertypes", supers);
                    row.put("annotations", annotationsOf(node.getModifiers(), path, unit, relPath));

                    List<Map<String, Object>> declared = new ArrayList<>();
                    for (Tree member : node.getMembers()) {
                        if (!(member instanceof MethodTree)) { continue; }
                        MethodTree m = (MethodTree) member;
                        TreePath mp = new TreePath(path, m);
                        Element me = trees.getElement(mp);
                        Map<String, Object> mrow = new LinkedHashMap<>();
                        mrow.put("name", m.getName().toString());
                        mrow.put("signature", me instanceof ExecutableElement
                                ? signature((ExecutableElement) me) : m.getName() + "(?)");
                        mrow.put("resolution", (ok && me instanceof ExecutableElement) ? "full" : "partial");
                        mrow.put("has_body", m.getBody() != null);
                        // what this member's declaration actually mentions:
                        // the locus a scope amendment has to be inside
                        List<String> refs = new ArrayList<>();
                        if (me instanceof ExecutableElement) {
                            ExecutableElement ee = (ExecutableElement) me;
                            refs.add(ee.getReturnType().toString());
                            for (Element pe : ee.getParameters()) { refs.add(pe.asType().toString()); }
                            for (TypeMirror th : ee.getThrownTypes()) { refs.add(th.toString()); }
                        }
                        mrow.put("type_refs", refs);
                        mrow.put("annotations", annotationsOf(m.getModifiers(), mp, unit, relPath));
                        declared.add(mrow);
                    }
                    row.put("declared", declared);

                    // What this type ACTUALLY inherits, asked of the compiler.
                    // Absence from the declaration is not evidence of it.
                    List<Map<String, Object>> inherited = new ArrayList<>();
                    if (ok) {
                        for (Element m : elements.getAllMembers(type)) {
                            if (m.getKind() != ElementKind.METHOD) { continue; }
                            if (m.getEnclosingElement().equals(type)) { continue; }
                            String owner = m.getEnclosingElement() instanceof TypeElement
                                    ? ((TypeElement) m.getEnclosingElement()).getQualifiedName().toString() : "";
                            if (owner.equals("java.lang.Object")) { continue; }
                            inherited.add(memberRow(task, type, (ExecutableElement) m, owner));
                        }
                    }
                    row.put("inherited", inherited);
                    // Everything the SUPERTYPES declare, overriding included: a
                    // member the type redeclares is still a member the platform
                    // can answer from above, and getAllMembers hides exactly
                    // that case behind the override.
                    List<Map<String, Object>> supertypeMethods = new ArrayList<>();
                    if (ok) {
                        TreeSet<String> seen = new TreeSet<>();
                        collectSupertypeMethods(task, type.asType(), type, supertypeMethods, seen);
                    }
                    row.put("supertype_methods", supertypeMethods);
                    row.put("inherited_known", ok);
                    types.add(row);
                    return super.visitClass(node, unused);
                }

                private List<Map<String, Object>> annotationsOf(ModifiersTree mods, TreePath owner,
                                                                CompilationUnitTree cu, String rp) {
                    List<Map<String, Object>> out = new ArrayList<>();
                    for (AnnotationTree a : mods.getAnnotations()) {
                        TreePath ap = new TreePath(owner, a);
                        TypeMirror tm = trees.getTypeMirror(ap);
                        Map<String, Object> row = new LinkedHashMap<>();
                        String fqn = tm == null ? "" : tm.toString();
                        row.put("fqn", fqn);
                        row.put("simple", fqn.isEmpty() ? a.getAnnotationType().toString()
                                : fqn.substring(fqn.lastIndexOf('.') + 1));
                        row.put("start", positions.getStartPosition(cu, a));
                        row.put("end", positions.getEndPosition(cu, a));
                        List<String> values = new ArrayList<>();
                        boolean literal = true;
                        for (ExpressionTree arg : a.getArguments()) {
                            literal &= collectLiterals(arg, values);
                        }
                        if (a.getArguments().isEmpty()) { literal = true; }
                        row.put("values", values);
                        // an argument that is not a string literal is a
                        // question this tool cannot answer, and it says so
                        row.put("resolution", (fqn.isEmpty() || !literal) ? "inconclusive" : "full");
                        out.add(row);
                    }
                    return out;
                }

                private boolean collectLiterals(Tree t, List<String> into) {
                    if (t instanceof LiteralTree) {
                        Object v = ((LiteralTree) t).getValue();
                        if (v instanceof String) { into.add((String) v); return true; }
                        return false;
                    }
                    switch (t.getKind()) {
                        case ASSIGNMENT:
                            return collectLiterals(((com.sun.source.tree.AssignmentTree) t).getExpression(), into);
                        case NEW_ARRAY: {
                            boolean all = true;
                            for (ExpressionTree e : ((com.sun.source.tree.NewArrayTree) t).getInitializers()) {
                                all &= collectLiterals(e, into);
                            }
                            return all;
                        }
                        default:
                            return false;
                    }
                }
            }.scan(unit, null);
        }

        Map<String, Object> doc = new LinkedHashMap<>();
        doc.put("schema", "rhoai3.dest-model/v1");
        doc.put("producer", "jdk-dest-model");
        doc.put("release", release);
        doc.put("classpath_used", classpath != null && Files.isReadable(classpath));
        doc.put("unresolved_files", new ArrayList<>(broken));
        doc.put("types", types);
        Files.createDirectories(out.toAbsolutePath().getParent());
        try (Writer w = Files.newBufferedWriter(out, StandardCharsets.UTF_8)) { writeJson(w, doc); }
    }

    private static void collectSupertypeMethods(JavacTask task, TypeMirror start, TypeElement self,
                                               List<Map<String, Object>> into, java.util.Set<String> seen) {
        for (TypeMirror sup : task.getTypes().directSupertypes(start)) {
            Element e = task.getTypes().asElement(sup);
            if (!(e instanceof TypeElement)) { continue; }
            TypeElement t = (TypeElement) e;
            String fqn = t.getQualifiedName().toString();
            if (fqn.equals("java.lang.Object") || !seen.add(fqn)) { continue; }
            for (Element m : t.getEnclosedElements()) {
                if (m.getKind() != ElementKind.METHOD) { continue; }
                into.add(memberRow(task, self, (ExecutableElement) m, fqn));
            }
            collectSupertypeMethods(task, sup, self, into, seen);
        }
    }

    /** A supertype method as DECLARED and as SEEN FROM the subtype.
     *
     * `JpaRepository<Vet,Integer>.save(T)` is `save(p.Vet)` for the type that
     * extends it, and an override is written with the substituted type. A
     * checker comparing the declared form would never match the override, and
     * one comparing only names would match every overload. */
    private static Map<String, Object> memberRow(JavacTask task, TypeElement owner, ExecutableElement m, String from) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("signature", signature(m));
        String asMember = signature(m);
        try {
            TypeMirror t = task.getTypes().asMemberOf((javax.lang.model.type.DeclaredType) owner.asType(), m);
            if (t instanceof javax.lang.model.type.ExecutableType) {
                javax.lang.model.type.ExecutableType et = (javax.lang.model.type.ExecutableType) t;
                StringBuilder sb = new StringBuilder(m.getSimpleName().toString()).append('(');
                boolean first = true;
                for (TypeMirror pt : et.getParameterTypes()) {
                    if (!first) { sb.append(','); }
                    sb.append(pt.toString());
                    first = false;
                }
                asMember = sb.append(')').toString();
            }
        } catch (IllegalArgumentException ignored) {
            // not a member of that type after all; the declared form stands
        }
        row.put("as_member", asMember);
        row.put("from", from);
        row.put("name", m.getSimpleName().toString());
        return row;
    }

    private static String rel(Path root, Path file) {
        try { return root.toAbsolutePath().relativize(file.toAbsolutePath()).toString().replace('\\', '/'); }
        catch (IllegalArgumentException e) { return file.toString(); }
    }

    private static String signature(ExecutableElement m) {
        StringBuilder sb = new StringBuilder(m.getSimpleName().toString()).append('(');
        boolean first = true;
        for (Element p : m.getParameters()) {
            if (!first) { sb.append(','); }
            sb.append(((javax.lang.model.element.VariableElement) p).asType().toString());
            first = false;
        }
        return sb.append(')').toString();
    }

    @SuppressWarnings("unchecked")
    private static void writeJson(Writer w, Object v) throws IOException {
        if (v == null) { w.write("null"); }
        else if (v instanceof Map) {
            w.write('{');
            boolean first = true;
            for (Map.Entry<String, Object> e : ((Map<String, Object>) v).entrySet()) {
                if (!first) { w.write(','); }
                writeString(w, e.getKey()); w.write(':'); writeJson(w, e.getValue());
                first = false;
            }
            w.write('}');
        } else if (v instanceof List) {
            w.write('[');
            boolean first = true;
            for (Object o : (List<Object>) v) { if (!first) { w.write(','); } writeJson(w, o); first = false; }
            w.write(']');
        } else if (v instanceof String) { writeString(w, (String) v); }
        else if (v instanceof Boolean || v instanceof Number) { w.write(String.valueOf(v)); }
        else { writeString(w, String.valueOf(v)); }
    }

    private static void writeString(Writer w, String s) throws IOException {
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
                    if (c < 0x20) { w.write(String.format("\\u%04x", (int) c)); } else { w.write(c); }
            }
        }
        w.write('"');
    }

    private DestModel() { }
}
