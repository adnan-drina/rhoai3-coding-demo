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
//   java DestModel --source <dir> --out <json> --release <n> [--classpath <file>] [--also-source <dir>]...
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
import javax.lang.model.type.TypeKind;
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

    private static final java.util.Set<String> FLOW_CODES = new java.util.HashSet<>(Arrays.asList(
            "compiler.err.unreported.exception.need.to.catch.or.throw",
            "compiler.err.unreported.exception.default.constructor",
            "compiler.err.unreported.exception.implicit.close",
            "compiler.err.var.might.not.have.been.initialized",
            "compiler.err.var.might.already.be.assigned",
            "compiler.err.missing.ret.stmt",
            "compiler.err.unreachable.stmt"));

    public static void main(String[] args) throws Exception {
        Path source = null, out = null, classpath = null;
        String release = "21";
        List<Path> alsoSources = new ArrayList<>();
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--source": source = Paths.get(args[++i]); break;
                // compiled together with --source so references resolve (the
                // collector compiles target/generated-sources too; without them
                // every generated DTO is a phantom error), never emitted
                case "--also-source": alsoSources.add(Paths.get(args[++i])); break;
                case "--out": out = Paths.get(args[++i]); break;
                case "--release": release = args[++i]; break;
                case "--classpath": classpath = Paths.get(args[++i]); break;
                default: throw new IllegalArgumentException("unknown argument " + args[i]);
            }
        }
        if (source == null || out == null) {
            System.err.println("usage: DestModel --source <dir> --out <json> [--release <n>] [--classpath <file>] [--also-source <dir>]...");
            System.exit(2);
        }
        List<Path> files;
        try (Stream<Path> walk = Files.walk(source)) {
            files = walk.filter(p -> p.toString().endsWith(".java")).sorted().collect(Collectors.toList());
        }
        final Path sourceRoot = source.toAbsolutePath().normalize();
        for (Path extra : alsoSources) {
            if (!Files.isDirectory(extra)) { continue; }
            try (Stream<Path> walk = Files.walk(extra)) {
                walk.filter(p -> p.toString().endsWith(".java")).sorted().forEach(files::add);
            }
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
        // Only ATTRIBUTION errors make a file untrustworthy. A flow-analysis
        // error -- an unreported checked exception, an uninitialized variable --
        // is raised after every name and type in the file has been resolved, and
        // it is precisely what unhandled_throws exists to enumerate. Counting it
        // as "broken" made the one file javac names the one file the model would
        // not speak about.
        TreeSet<String> broken = new TreeSet<>();
        for (Diagnostic<? extends JavaFileObject> d : diags.getDiagnostics()) {
            if (d.getKind() == Diagnostic.Kind.ERROR && d.getSource() != null && !FLOW_CODES.contains(String.valueOf(d.getCode()))) {
                broken.add(rel(source, Paths.get(d.getSource().toUri())));
            }
        }

        List<Map<String, Object>> types = new ArrayList<>();
        Path root = source;
        for (CompilationUnitTree unit : units) {
            Path file = Paths.get(unit.getSourceFile().toUri());
            if (!file.toAbsolutePath().normalize().startsWith(sourceRoot)) { continue; }  // an --also-source unit
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
                    List<Map<String, Object>> unhandled = new ArrayList<>();
                    for (Tree member : node.getMembers()) {
                        // field initializers and initializer blocks can call a
                        // throwing method too; their sites are enumerated, and a
                        // checked exception there is never claimed as handled
                        if (member instanceof com.sun.source.tree.VariableTree) {
                            com.sun.source.tree.VariableTree v = (com.sun.source.tree.VariableTree) member;
                            if (v.getInitializer() != null) {
                                scanBody(task, trees, elements, positions, unit,
                                        new TreePath(new TreePath(path, member), v.getInitializer()),
                                        "<field:" + v.getName() + ">", ok, new ArrayList<>(), unhandled);
                            }
                            continue;
                        }
                        if (member instanceof com.sun.source.tree.BlockTree) {
                            scanBody(task, trees, elements, positions, unit, new TreePath(path, member),
                                    "<initializer>", ok, new ArrayList<>(), unhandled);
                            continue;
                        }
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
                        // the CHECKED exceptions this member declares. Adding one to an
                        // existing member introduces a checked exception even though no
                        // call site inside it is unhandled any more.
                        List<String> throwsChecked = new ArrayList<>();
                        if (me instanceof ExecutableElement) {
                            TypeElement rte = elements.getTypeElement("java.lang.RuntimeException");
                            TypeElement err = elements.getTypeElement("java.lang.Error");
                            for (TypeMirror th : ((ExecutableElement) me).getThrownTypes()) {
                                boolean unchecked = (rte != null && task.getTypes().isSubtype(th, rte.asType()))
                                        || (err != null && task.getTypes().isSubtype(th, err.asType()));
                                if (!unchecked) { throwsChecked.add(th.toString()); }
                            }
                        }
                        mrow.put("throws_checked", throwsChecked);
                        mrow.put("annotations", annotationsOf(m.getModifiers(), mp, unit, relPath));
                        com.sun.source.tree.LineMap lines = unit.getLineMap();
                        long ms = positions.getStartPosition(unit, m), mend = positions.getEndPosition(unit, m);
                        mrow.put("start_line", ms >= 0 ? lines.getLineNumber(ms) : -1);
                        mrow.put("end_line", mend >= 0 ? lines.getLineNumber(mend) : -1);
                        List<String> calls = new ArrayList<>();
                        if (m.getBody() != null) {
                            scanBody(task, trees, elements, positions, unit, new TreePath(mp, m.getBody()),
                                    String.valueOf(mrow.get("signature")), ok, calls, unhandled);
                        }
                        mrow.put("calls", calls);
                        // what the body CALLS BY NAME, from the parse tree alone. Attribution
                        // can fail (an unresolved type) and leave a call unnamed in `calls`;
                        // the parse tree cannot, so a baseline member that made no call named
                        // URI cannot have held an unhandled URI(String) site.
                        final List<String> callNames = new ArrayList<>();
                        if (m.getBody() != null) {
                            new com.sun.source.util.TreeScanner<Void, Void>() {
                                @Override public Void visitClass(ClassTree n, Void v) { return null; }
                                @Override public Void visitMethodInvocation(com.sun.source.tree.MethodInvocationTree n, Void v) {
                                    ExpressionTree sel = n.getMethodSelect();
                                    callNames.add(sel instanceof com.sun.source.tree.MemberSelectTree
                                            ? ((com.sun.source.tree.MemberSelectTree) sel).getIdentifier().toString()
                                            : sel.toString());
                                    return super.visitMethodInvocation(n, v);
                                }
                                @Override public Void visitNewClass(com.sun.source.tree.NewClassTree n, Void v) {
                                    Tree id = n.getIdentifier();
                                    if (id instanceof com.sun.source.tree.ParameterizedTypeTree) {
                                        id = ((com.sun.source.tree.ParameterizedTypeTree) id).getType();
                                    }
                                    callNames.add(id instanceof com.sun.source.tree.MemberSelectTree
                                            ? ((com.sun.source.tree.MemberSelectTree) id).getIdentifier().toString()
                                            : id.toString());
                                    return super.visitNewClass(n, v);
                                }
                            }.scan(m.getBody(), null);
                        }
                        mrow.put("call_names", callNames);
                        declared.add(mrow);
                    }
                    row.put("declared", declared);
                    // Every call site whose resolved callee declares a checked
                    // exception that nothing encloses: no enclosing try catches it
                    // and the member does not declare it. javac reports these one
                    // at a time (flow analysis), so a diagnostic count can never
                    // stand in for this list. Handled sites are not listed.
                    row.put("unhandled_throws", unhandled);

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

    /** Resolved calls and unhandled checked-exception sites in one member body. */
    private static void scanBody(JavacTask task, Trees trees, Elements elements, SourcePositions positions,
                                 CompilationUnitTree unit, TreePath start, String member, boolean ok,
                                 List<String> calls, List<Map<String, Object>> sites) {
        javax.lang.model.util.Types types = task.getTypes();
        TypeElement thr = elements.getTypeElement("java.lang.Throwable");
        TypeElement rte = elements.getTypeElement("java.lang.RuntimeException");
        TypeElement err = elements.getTypeElement("java.lang.Error");
        if (thr == null || rte == null || err == null) { return; }
        final TypeMirror throwable = thr.asType(), runtime = rte.asType(), error = err.asType();
        final Map<String, Integer> seen = new java.util.HashMap<>();
        final com.sun.source.tree.LineMap lines = unit.getLineMap();
        new TreePathScanner<Void, Void>() {
            // a nested or anonymous class is its own row
            @Override public Void visitClass(ClassTree node, Void p) { return null; }

            @Override public Void visitMethodInvocation(com.sun.source.tree.MethodInvocationTree node, Void p) {
                site(node);
                return super.visitMethodInvocation(node, p);
            }

            @Override public Void visitNewClass(com.sun.source.tree.NewClassTree node, Void p) {
                site(node);
                return super.visitNewClass(node, p);
            }

            private String nameOf(ExecutableElement callee) {
                String owner = callee.getEnclosingElement() instanceof TypeElement
                        ? ((TypeElement) callee.getEnclosingElement()).getQualifiedName().toString() : "";
                return owner + "." + signature(callee);
            }

            private void site(Tree node) {
                Element e = trees.getElement(getCurrentPath());
                if (!(e instanceof ExecutableElement)) { return; }
                ExecutableElement callee = (ExecutableElement) e;
                String name = nameOf(callee);
                calls.add(name);
                // occurrence counts every call of this callee in the member, so
                // wrapping one of them in a try does not renumber the others
                int occurrence = seen.merge(name, 1, Integer::sum) - 1;
                for (TypeMirror t : callee.getThrownTypes()) {
                    if (t.getKind() != TypeKind.DECLARED) {
                        record(node, name, t.toString(), "inconclusive", occurrence);
                        continue;
                    }
                    if (!types.isSubtype(t, throwable) || types.isSubtype(t, runtime) || types.isSubtype(t, error)) {
                        continue;  // unchecked
                    }
                    String state = handled(t);
                    if (!"handled".equals(state)) { record(node, name, t.toString(), state, occurrence); }
                }
            }

            private String handled(TypeMirror t) {
                Tree child = getCurrentPath().getLeaf();
                for (TreePath p = getCurrentPath().getParentPath(); p != null; p = p.getParentPath()) {
                    Tree leaf = p.getLeaf();
                    if (leaf instanceof com.sun.source.tree.TryTree) {
                        com.sun.source.tree.TryTree tt = (com.sun.source.tree.TryTree) leaf;
                        boolean covered = child == tt.getBlock() || tt.getResources().contains(child);
                        if (covered) {
                            for (com.sun.source.tree.CatchTree c : tt.getCatches()) {
                                TypeMirror ct = trees.getTypeMirror(new TreePath(new TreePath(p, c), c.getParameter()));
                                // a catch type the compiler could not resolve might be the one
                                // that handles this: undecided, never "unhandled"
                                if (ct == null || ct.getKind() == TypeKind.ERROR) { return "inconclusive"; }
                                if (ct.getKind() == TypeKind.UNION) {
                                    for (TypeMirror alt : ((javax.lang.model.type.UnionType) ct).getAlternatives()) {
                                        if (alt.getKind() == TypeKind.ERROR) { return "inconclusive"; }
                                        if (types.isSubtype(t, alt)) { return "handled"; }
                                    }
                                } else if (types.isSubtype(t, ct)) {
                                    return "handled";
                                }
                            }
                        }
                    } else if (leaf instanceof com.sun.source.tree.LambdaExpressionTree) {
                        return "inconclusive";  // the functional interface decides; not claimed either way
                    } else if (leaf instanceof MethodTree) {
                        Element me = trees.getElement(p);
                        if (!(me instanceof ExecutableElement)) { return "inconclusive"; }
                        boolean undecided = false;
                        for (TypeMirror d : ((ExecutableElement) me).getThrownTypes()) {
                            if (d.getKind() == TypeKind.ERROR) { undecided = true; continue; }
                            if (types.isSubtype(t, d)) { return "handled"; }
                        }
                        return undecided ? "inconclusive" : "unhandled";
                    } else if (leaf instanceof ClassTree) {
                        return "inconclusive";  // a field initializer or initializer block
                    }
                    child = leaf;
                }
                return "inconclusive";
            }

            private void record(Tree node, String callee, String exception, String state, int occurrence) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("member", member);
                row.put("callee", callee);
                row.put("exception", exception);
                row.put("occurrence", occurrence);
                row.put("state", state);
                row.put("file_resolution", ok ? "full" : "partial");
                long s = positions.getStartPosition(unit, node), en = positions.getEndPosition(unit, node);
                row.put("start", s);
                row.put("end", en);
                row.put("line", s >= 0 ? lines.getLineNumber(s) : -1);
                row.put("end_line", en >= 0 ? lines.getLineNumber(en) : -1);
                // the operation that consumes this value, when it is a call argument:
                // what a repair must preserve (e.g. HttpHeaders.setLocation(URI))
                String consumer = "";
                TreePath parent = getCurrentPath().getParentPath();
                if (parent != null && parent.getLeaf() instanceof com.sun.source.tree.MethodInvocationTree
                        && ((com.sun.source.tree.MethodInvocationTree) parent.getLeaf()).getArguments().contains(node)) {
                    Element ce = trees.getElement(parent);
                    if (ce instanceof ExecutableElement) { consumer = nameOf((ExecutableElement) ce); }
                }
                row.put("consumer", consumer);
                sites.add(row);
            }
        }.scan(start, null);
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
