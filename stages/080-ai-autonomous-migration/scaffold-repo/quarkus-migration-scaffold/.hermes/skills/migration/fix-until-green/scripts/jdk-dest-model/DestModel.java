// DestModel: the DESTINATION's own structure, from the JDK's compiler API.
//
// The M1 extractor models the frozen SOURCE and is pinned to that job. The
// loop needs the same kind of truth about the tree it is editing right now:
// which members a repository actually declares, which it actually inherits,
// exactly where each profile condition sits, and what each FIELD's annotations
// say. Regex answered those questions wrongly in every direction -- it read a
// fully qualified annotation as absent, a redeclared findAll as underivable,
// and a deleted member as inherited -- and the source model cannot answer them
// at all, because a worker's edit changes the destination and not the source
// (v9: @Value("#{servletContext.contextPath}") in the frozen source, @Value("")
// on disk, and a config property with an empty name at startup).
//
// Everything here is resolved by javac. A declaration javac could not
// resolve, or an annotation argument that is not a string literal, is
// reported INCONCLUSIVE and never as a pass: the caller must refuse rather
// than guess.
//
//   java DestModel --source <dir> --out <json> --release <n> [--classpath <file>] [--also-source <dir>]...
//                  [--type-ref-budget <nodes>]   (tests only: force the node bound)
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
import javax.lang.model.element.TypeParameterElement;
import javax.lang.model.element.Parameterizable;
import javax.lang.model.type.ArrayType;
import javax.lang.model.type.DeclaredType;
import javax.lang.model.type.IntersectionType;
import javax.lang.model.type.TypeKind;
import javax.lang.model.type.TypeMirror;
import javax.lang.model.type.TypeVariable;
import javax.lang.model.type.UnionType;
import javax.lang.model.type.WildcardType;
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

    // The declaration-reference walk (types[].type_refs) is FINITE by
    // construction: a mirror deeper than this, or more mirrors than this in one
    // type's declarations, ends the walk as INCOMPLETE -- never as an empty,
    // complete answer. Both are far above any declaration a person writes.
    static final int TYPE_REF_MAX_DEPTH = 32;
    static final int TYPE_REF_MAX_NODES = 20000;

    public static void main(String[] args) throws Exception {
        Path source = null, out = null, classpath = null;
        String release = "21";
        int typeRefBudget = TYPE_REF_MAX_NODES;
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
                case "--type-ref-budget": typeRefBudget = Integer.parseInt(args[++i]); break;
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
        List<CompilationUnitTree> units = new ArrayList<>();
        task.parse().forEach(units::add);
        // Parse evidence is independent of attribution. A migration unit can
        // retire an annotation while unrelated unresolved types remain. Save
        // every identifier BEFORE analyze mutates the AST; a parse error never
        // supplies evidence that a name is absent.
        TreeSet<String> parseBroken = new TreeSet<>();
        for (Diagnostic<? extends JavaFileObject> d : diags.getDiagnostics()) {
            if (d.getKind() == Diagnostic.Kind.ERROR && d.getSource() != null) {
                parseBroken.add(rel(source, Paths.get(d.getSource().toUri())));
            }
        }
        Map<String, List<String>> syntaxNames = new LinkedHashMap<>();
        Map<String, List<String>> syntaxQualifiedNames = new LinkedHashMap<>();
        Map<String, Boolean> syntaxImplicitTypes = new LinkedHashMap<>();
        for (CompilationUnitTree unit : units) {
            TreeSet<String> names = new TreeSet<>();
            TreeSet<String> qualified = new TreeSet<>();
            if (unit.getPackageName() != null) { qualified.add(unit.getPackageName().toString()); }
            boolean[] implicitTypes = {false};
            for (com.sun.source.tree.ImportTree imp : unit.getImports()) {
                if (imp.isStatic()) { implicitTypes[0] = true; }
            }
            new com.sun.source.util.TreeScanner<Void, Void>() {
                @Override public Void visitClass(ClassTree n, Void v) {
                    names.add(n.getSimpleName().toString());
                    // Inherited/anonymous member types and static imports can
                    // name a foreign type without naming its package. A
                    // package-absence proof must not guess their attribution.
                    if (n.getExtendsClause() != null || !n.getImplementsClause().isEmpty()
                            || n.getSimpleName().length() == 0) { implicitTypes[0] = true; }
                    return super.visitClass(n, v);
                }
                @Override public Void visitIdentifier(com.sun.source.tree.IdentifierTree n, Void v) {
                    names.add(n.getName().toString());
                    return super.visitIdentifier(n, v);
                }
                @Override public Void visitMemberSelect(com.sun.source.tree.MemberSelectTree n, Void v) {
                    names.add(n.getIdentifier().toString());
                    qualified.add(n.toString());
                    return super.visitMemberSelect(n, v);
                }
            }.scan(unit, null);
            syntaxNames.put(rel(source, Paths.get(unit.getSourceFile().toUri())), new ArrayList<>(names));
            syntaxQualifiedNames.put(rel(source, Paths.get(unit.getSourceFile().toUri())), new ArrayList<>(qualified));
            syntaxImplicitTypes.put(rel(source, Paths.get(unit.getSourceFile().toUri())), implicitTypes[0]);
        }
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
        final int refBudget = typeRefBudget;
        for (CompilationUnitTree unit : units) {
            Path file = Paths.get(unit.getSourceFile().toUri());
            if (!file.toAbsolutePath().normalize().startsWith(sourceRoot)) { continue; }  // an --also-source unit
            String relPath = rel(root, file);
            boolean ok = !broken.contains(relPath);
            // The import list, so a caller can bind a simple annotation name
            // to its type even in a tree that cannot yet be compiled against
            // its dependencies (the bootstrap runs before the first build).
            List<String> imports = new ArrayList<>();
            boolean[] implicitComplete = {true};
            for (com.sun.source.tree.ImportTree imp : unit.getImports()) {
                imports.add(imp.getQualifiedIdentifier().toString());
                if (imp.isStatic()) { implicitComplete[0] = false; }
            }
            // A broken field or annotation need not make the hierarchy of
            // member TYPE names unknowable. Resolve that narrower question
            // independently; do not promote method/call/inheritance evidence
            // below to full resolution. Include every nested class's scope.
            TreeSet<String> implicitNames = new TreeSet<>();
            TreeSet<String> implicitResolved = new TreeSet<>();
            new TreePathScanner<Void, Void>() {
                @Override public Void visitClass(ClassTree node, Void unused) {
                    Element el = trees.getElement(getCurrentPath());
                    if (!(el instanceof TypeElement) || !collectImplicitTypeNames(task, el.asType(),
                            implicitNames, new TreeSet<>(), implicitResolved)) { implicitComplete[0] = false; }
                    return super.visitClass(node, unused);
                }
            }.scan(unit, null);
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
                    row.put("syntax_complete", !parseBroken.contains(relPath));
                    row.put("syntax_names", syntaxNames.get(relPath));
                    row.put("syntax_qualified_names", syntaxQualifiedNames.get(relPath));
                    row.put("syntax_implicit_types", syntaxImplicitTypes.get(relPath));
                    row.put("implicit_type_scope_complete", implicitComplete[0]);
                    row.put("implicit_type_names", new ArrayList<>(implicitNames));
                    row.put("imports", imports);
                    List<String> supers = new ArrayList<>();
                    if (type.getSuperclass() != null && type.getSuperclass().getKind().name().equals("DECLARED")) {
                        supers.add(type.getSuperclass().toString());
                    }
                    for (TypeMirror itf : type.getInterfaces()) { supers.add(itf.toString()); }
                    row.put("supertypes", supers);
                    row.put("annotations", annotationsOf(node.getModifiers(), path, unit, relPath));
                    // What this type's DECLARATIONS name, from the compiler's
                    // mirrors: the supertypes, the type parameters' bounds, and
                    // below every field type and member signature.
                    RefWalk refWalk = new RefWalk(refBudget);
                    refWalk.walk(type.getSuperclass(), "extends");
                    for (TypeMirror itf : type.getInterfaces()) { refWalk.walk(itf, "implements"); }
                    for (TypeParameterElement tp : type.getTypeParameters()) {
                        refWalk.walk(tp.asType(), "type-parameter:" + tp.getSimpleName());
                    }

                    List<Map<String, Object>> declared = new ArrayList<>();
                    List<Map<String, Object>> fields = new ArrayList<>();
                    List<Map<String, Object>> unhandled = new ArrayList<>();
                    for (Tree member : node.getMembers()) {
                        // field initializers and initializer blocks can call a
                        // throwing method too; their sites are enumerated, and a
                        // checked exception there is never claimed as handled
                        if (member instanceof com.sun.source.tree.VariableTree) {
                            com.sun.source.tree.VariableTree v = (com.sun.source.tree.VariableTree) member;
                            // A field's annotations are facts about the tree AS IT
                            // IS NOW. The frozen source's model cannot answer for
                            // them: on destination v9 the boot gate died on an
                            // empty config property name because a worker had
                            // replaced @Value("#{servletContext.contextPath}")
                            // with @Value(""), and the source model -- which still
                            // carried the SpEL -- located nothing.
                            Map<String, Object> frow = new LinkedHashMap<>();
                            frow.put("name", v.getName().toString());
                            frow.put("type", v.getType() == null ? "" : v.getType().toString());
                            String constant = stringConstant(v, path);
                            if (constant != null) { frow.put("constant", constant); }
                            frow.put("annotations", annotationsOf(v.getModifiers(), new TreePath(path, member), unit, relPath));
                            Element fieldEl = trees.getElement(new TreePath(path, member));
                            if (fieldEl == null) { refWalk.unknown("field:" + v.getName(), "unattributed"); }
                            else { refWalk.walk(fieldEl.asType(), "field:" + v.getName()); }
                            fields.add(frow);
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
                            String locus = "member:" + signature(ee);
                            refWalk.walk(ee.getReturnType(), locus);
                            for (Element pe : ee.getParameters()) { refWalk.walk(pe.asType(), locus); }
                            for (TypeMirror th : ee.getThrownTypes()) { refWalk.walk(th, locus); }
                            for (TypeParameterElement tp : ee.getTypeParameters()) { refWalk.walk(tp.asType(), locus); }
                        } else {
                            refWalk.unknown("member:" + m.getName(), "unattributed");
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
                        // the PARAMETERS, each with its own annotations: a
                        // generated DTO's @JsonCreator constructor says which
                        // properties a request body must carry only here
                        // (@JsonProperty(required = true, value = "…")), and a
                        // handler's parameter list is what the compat layer binds
                        List<Map<String, Object>> params = new ArrayList<>();
                        for (com.sun.source.tree.VariableTree pv : m.getParameters()) {
                            Map<String, Object> prow = new LinkedHashMap<>();
                            prow.put("name", pv.getName().toString());
                            Element pel = trees.getElement(new TreePath(mp, pv));
                            prow.put("type", pel != null ? pel.asType().toString()
                                    : (pv.getType() == null ? "" : pv.getType().toString()));
                            prow.put("annotations", annotationsOf(pv.getModifiers(), new TreePath(mp, pv), unit, relPath));
                            params.add(prow);
                        }
                        mrow.put("params", params);
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
                        List<String> guards = m.getBody() == null ? List.of()
                                : validationGuards(task, trees, unit, new TreePath(mp, m.getBody()));
                        if (!guards.isEmpty()) { mrow.put("validation_guards", guards); }
                        declared.add(mrow);
                    }
                    row.put("declared", declared);
                    // every FIELD this type declares, with what its annotations
                    // say -- string-literal arguments only, as above
                    row.put("fields", fields);
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
                    // Additive facts. `type_refs_complete` is about THIS walk
                    // only; `resolution` above stays the compiler's own answer.
                    row.put("type_refs", new ArrayList<>(refWalk.refs));
                    row.put("type_refs_complete", refWalk.incomplete.isEmpty());
                    row.put("type_refs_incomplete", refWalk.incompleteRows());
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
                        // and WHICH ATTRIBUTE each literal was written for. A
                        // flat value list cannot say whether the first literal of
                        // @ConfigProperty(name = "x", defaultValue = "d") is the
                        // property or the default, and picking by position would
                        // be a guess. An attribute whose argument is not a string
                        // literal is absent from the map, never present-and-wrong.
                        Map<String, Object> named = new LinkedHashMap<>();
                        // the CLASS LITERALS an attribute was written with,
                        // each as the type the compiler resolved it to:
                        // @Typed(PetRepositoryImpl.class) restricts a bean's
                        // types to exactly that class (CDI 4.1, Restricting
                        // the bean types of a bean), and only a resolved type
                        // can be compared with the one an obligation names.
                        // An attribute with any other kind of element, or a
                        // literal the compiler could not resolve, is absent.
                        Map<String, Object> classes = new LinkedHashMap<>();
                        boolean literal = true;
                        for (ExpressionTree arg : a.getArguments()) {
                            String attr = "value";
                            Tree expr = arg;
                            TreePath argPath = new TreePath(ap, arg);
                            TreePath exprPath = argPath;
                            if (arg.getKind() == Tree.Kind.ASSIGNMENT) {
                                com.sun.source.tree.AssignmentTree as = (com.sun.source.tree.AssignmentTree) arg;
                                attr = as.getVariable().toString();
                                expr = as.getExpression();
                                exprPath = new TreePath(argPath, expr);
                            }
                            List<String> classLiterals = new ArrayList<>();
                            if (collectClassLiterals(exprPath, classLiterals) && !classLiterals.isEmpty()) {
                                classes.put(attr, classLiterals);
                            }
                            List<String> mine = new ArrayList<>();
                            // `values` keeps the String literals it always
                            // carried; `named` also holds a boolean or numeric
                            // literal spelled as written (required = true),
                            // because a @JsonProperty(required = true) is a
                            // fact about what a body must carry
                            List<String> scalars = new ArrayList<>();
                            boolean ofLiterals = collectLiterals(expr, mine, scalars);
                            literal &= ofLiterals;
                            values.addAll(mine);
                            if (ofLiterals) { named.put(attr, scalars); }
                        }
                        if (a.getArguments().isEmpty()) { literal = true; }
                        row.put("values", values);
                        row.put("named", named);
                        if (!classes.isEmpty()) { row.put("classes", classes); }
                        // an argument that is not a string literal is a
                        // question this tool cannot answer, and it says so
                        row.put("resolution", (fqn.isEmpty() || !literal) ? "inconclusive" : "full");
                        out.add(row);
                    }
                    return out;
                }

                /**
                 * The compile-time String value a field's own initializer
                 * states, or null.
                 *
                 * The same fact M1's extractor records about the frozen
                 * source, asked of the tree in front of us: a run whose
                 * SEALED structure model predates that key still has a
                 * constants type on disk, and an authorization expression
                 * naming @roles.VET_ADMIN carries the reference and not the
                 * role. getConstantValue() is the folded value of a constant
                 * variable (JLS 4.12.4); when attribution folded nothing --
                 * this tool runs over trees that do not resolve -- a final
                 * field's declaration tree still holds its literal. Anything
                 * else is not a constant and the key is absent.
                 */
                private String stringConstant(com.sun.source.tree.VariableTree v, TreePath owner) {
                    Element el = trees.getElement(new TreePath(owner, v));
                    if (el instanceof javax.lang.model.element.VariableElement) {
                        Object folded = ((javax.lang.model.element.VariableElement) el).getConstantValue();
                        if (folded != null) { return folded instanceof String ? (String) folded : null; }
                    }
                    if (!v.getModifiers().getFlags().contains(javax.lang.model.element.Modifier.FINAL)) { return null; }
                    ExpressionTree init = v.getInitializer();
                    if (!(init instanceof LiteralTree)) { return null; }
                    Object value = ((LiteralTree) init).getValue();
                    return value instanceof String ? (String) value : null;
                }

                private boolean collectClassLiterals(TreePath p, List<String> out) {
                    Tree t = p.getLeaf();
                    if (t instanceof com.sun.source.tree.MemberSelectTree
                            && ((com.sun.source.tree.MemberSelectTree) t).getIdentifier().contentEquals("class")) {
                        TypeMirror tm = trees.getTypeMirror(
                                new TreePath(p, ((com.sun.source.tree.MemberSelectTree) t).getExpression()));
                        if (tm == null || tm.getKind() == TypeKind.ERROR) { return false; }
                        out.add(task.getTypes().erasure(tm).toString());
                        return true;
                    }
                    if (t.getKind() == Tree.Kind.NEW_ARRAY) {
                        boolean all = true;
                        for (ExpressionTree e : ((com.sun.source.tree.NewArrayTree) t).getInitializers()) {
                            all &= collectClassLiterals(new TreePath(p, e), out);
                        }
                        return all;
                    }
                    return false;
                }

                private boolean collectLiterals(Tree t, List<String> strings, List<String> scalars) {
                    if (t instanceof LiteralTree) {
                        Object v = ((LiteralTree) t).getValue();
                        if (v instanceof String) { strings.add((String) v); scalars.add((String) v); return true; }
                        if (v instanceof Boolean || v instanceof Number || v instanceof Character) {
                            scalars.add(String.valueOf(v));
                            return true;
                        }
                        return false;
                    }
                    switch (t.getKind()) {
                        case ASSIGNMENT:
                            return collectLiterals(((com.sun.source.tree.AssignmentTree) t).getExpression(), strings, scalars);
                        case NEW_ARRAY: {
                            boolean all = true;
                            for (ExpressionTree e : ((com.sun.source.tree.NewArrayTree) t).getInitializers()) {
                                all &= collectLiterals(e, strings, scalars);
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

    /**
     * The VALIDATION GUARDS of one member body: every `if` condition that
     * decides on bean-validation errors, as a boolean skeleton the Spring
     * source and its Quarkus translation can be compared by (V16-8).
     *
     * `bindingResult.hasErrors()` (org.springframework.validation Errors or
     * BindingResult) is the atom INVALID; `validator.validate(x).isEmpty()`
     * (jakarta/javax.validation.Validator), directly or through a local the
     * member initialized from validate(), is !INVALID. `!`, `||`, `&&` and
     * parentheses keep their structure; every other operand is its own
     * compiler-printed source text, so `x.getId() != null` stays itself. A
     * type the compiler could not resolve (a source tree modelled without its
     * classpath) is named through the file's own single-type imports.
     */
    private static List<String> validationGuards(JavacTask task, Trees trees, CompilationUnitTree unit, TreePath body) {
        Map<String, String> imports = new LinkedHashMap<>();
        for (com.sun.source.tree.ImportTree it : unit.getImports()) {
            if (it.isStatic()) { continue; }
            String q = it.getQualifiedIdentifier().toString();
            if (!q.endsWith(".*")) { imports.put(q.substring(q.lastIndexOf('.') + 1), q); }
        }
        java.util.Set<String> violationLocals = new java.util.HashSet<>();
        List<String> out = new ArrayList<>();
        new TreePathScanner<Void, Void>() {
            @Override public Void visitVariable(com.sun.source.tree.VariableTree v, Void x) {
                ExpressionTree init = v.getInitializer();
                if (init != null && isValidate(new TreePath(getCurrentPath(), init))) {
                    violationLocals.add(v.getName().toString());
                }
                return super.visitVariable(v, x);
            }
            @Override public Void visitIf(com.sun.source.tree.IfTree n, Void x) {
                String g = skeleton(new TreePath(getCurrentPath(), n.getCondition()));
                if (g.contains("INVALID")) { out.add(g); }
                return super.visitIf(n, x);
            }
            private String typeOf(TreePath p) {
                TypeMirror tm = trees.getTypeMirror(p);
                if (tm == null) { return ""; }
                String t = task.getTypes().erasure(tm).toString();
                return t.contains(".") ? t : imports.getOrDefault(t, t);
            }
            private boolean invokes(TreePath p, String name, String... owners) {
                Tree t = p.getLeaf();
                if (!(t instanceof com.sun.source.tree.MethodInvocationTree)) { return false; }
                ExpressionTree sel = ((com.sun.source.tree.MethodInvocationTree) t).getMethodSelect();
                if (!(sel instanceof com.sun.source.tree.MemberSelectTree)
                        || !((com.sun.source.tree.MemberSelectTree) sel).getIdentifier().contentEquals(name)) { return false; }
                Element el = trees.getElement(p);
                String owner = (el != null && el.getEnclosingElement() instanceof TypeElement)
                        ? ((TypeElement) el.getEnclosingElement()).getQualifiedName().toString() : "";
                String recv = typeOf(new TreePath(new TreePath(p, sel), ((com.sun.source.tree.MemberSelectTree) sel).getExpression()));
                for (String o : owners) { if (o.equals(owner) || o.equals(recv)) { return true; } }
                return false;
            }
            private boolean isValidate(TreePath p) {
                return invokes(p, "validate", "jakarta.validation.Validator", "javax.validation.Validator");
            }
            private boolean isViolations(TreePath p) {
                Tree t = p.getLeaf();
                if (t instanceof com.sun.source.tree.IdentifierTree) {
                    return violationLocals.contains(((com.sun.source.tree.IdentifierTree) t).getName().toString());
                }
                return isValidate(p);
            }
            private String neg(String s) {
                return s.startsWith("!") && !s.startsWith("!(") ? s.substring(1)
                        : (s.startsWith("!(") && s.endsWith(")") && balanced(s.substring(2, s.length() - 1)))
                          ? s.substring(2, s.length() - 1) : (s.startsWith("(") || !s.contains(" ") ? "!" + s : "!(" + s + ")");
            }
            private boolean balanced(String s) {
                int d = 0;
                for (char c : s.toCharArray()) { if (c == '(') { d++; } else if (c == ')') { if (--d < 0) { return false; } } }
                return d == 0;
            }
            private String skeleton(TreePath p) {
                Tree t = p.getLeaf();
                switch (t.getKind()) {
                    case PARENTHESIZED:
                        return skeleton(new TreePath(p, ((com.sun.source.tree.ParenthesizedTree) t).getExpression()));
                    case LOGICAL_COMPLEMENT:
                        return neg(skeleton(new TreePath(p, ((com.sun.source.tree.UnaryTree) t).getExpression())));
                    case CONDITIONAL_OR:
                    case CONDITIONAL_AND: {
                        com.sun.source.tree.BinaryTree b = (com.sun.source.tree.BinaryTree) t;
                        return "(" + skeleton(new TreePath(p, b.getLeftOperand()))
                                + (t.getKind() == Tree.Kind.CONDITIONAL_OR ? " || " : " && ")
                                + skeleton(new TreePath(p, b.getRightOperand())) + ")";
                    }
                    case METHOD_INVOCATION: {
                        if (invokes(p, "hasErrors", "org.springframework.validation.Errors",
                                "org.springframework.validation.BindingResult")) { return "INVALID"; }
                        ExpressionTree sel = ((com.sun.source.tree.MethodInvocationTree) t).getMethodSelect();
                        if (sel instanceof com.sun.source.tree.MemberSelectTree
                                && ((com.sun.source.tree.MemberSelectTree) sel).getIdentifier().contentEquals("isEmpty")
                                && isViolations(new TreePath(new TreePath(p, sel),
                                        ((com.sun.source.tree.MemberSelectTree) sel).getExpression()))) {
                            return "!INVALID";
                        }
                        return "{" + t.toString().replaceAll("\\s+", " ") + "}";
                    }
                    default:
                        return "{" + t.toString().replaceAll("\\s+", " ") + "}";
                }
            }
        }.scan(body, null);
        return out;
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

    /**
     * The declared types one type's DECLARATIONS name, asked of the compiler's
     * mirrors: generic arguments, array components, wildcard bounds, type
     * variable bounds, every bound of an intersection and the enclosing type of
     * a nested parameterized type. A field spelled {@code java.util.List<inside.A>}
     * names inside.A; its source spelling, erased, names only java.util.List
     * (rgctl offline evaluation 2026-09-25, G03G/G03A/G03N).
     *
     * Three outcomes, never conflated: a resolved reference (in {@link #refs}),
     * a complete walk that found nothing more, and incomplete evidence (in
     * {@link #incomplete}, with where and why). An unknown part never removes
     * a reference already established, and an error spelling is never emitted
     * as a resolved name.
     *
     * Termination does not rest on mirror identity (the API does not promise
     * one mirror per type): a type variable is expanded once per walk, keyed by
     * the declaration that binds it and its position there, so {@code T extends
     * Comparable<T>} ends where it began and two different {@code T}s are two
     * keys. The walk is an explicit stack with a depth and a node bound; hitting
     * either is recorded as incomplete. It reads only what the declarations
     * state -- never the members or ancestors of a referenced type, which would
     * turn a direct reference into a transitive closure.
     */
    static final class RefWalk {
        final java.util.TreeSet<String> refs = new java.util.TreeSet<>();
        final java.util.TreeSet<String> incomplete = new java.util.TreeSet<>();
        private final java.util.Set<List<Object>> expanded = new java.util.HashSet<>();
        private final int budget;
        private int nodes;

        RefWalk(int budget) { this.budget = budget; }

        void unknown(String locus, String reason) { incomplete.add(locus + "\u0000" + reason); }

        List<Map<String, Object>> incompleteRows() {
            List<Map<String, Object>> out = new ArrayList<>();
            for (String s : incomplete) {
                int i = s.indexOf('\u0000');
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("locus", s.substring(0, i));
                row.put("reason", s.substring(i + 1));
                out.add(row);
            }
            return out;
        }

        void walk(TypeMirror start, String locus) {
            if (start == null) { unknown(locus, "unattributed"); return; }
            java.util.ArrayDeque<Object[]> stack = new java.util.ArrayDeque<>();
            stack.push(new Object[] {start, 0});
            while (!stack.isEmpty()) {
                Object[] frame = stack.pop();
                TypeMirror tm = (TypeMirror) frame[0];
                int depth = (Integer) frame[1];
                if (tm == null) { continue; }  // an absent optional part (a wildcard's missing bound)
                if (nodes >= budget) { unknown(locus, "node-limit"); return; }
                nodes++;
                if (depth > TYPE_REF_MAX_DEPTH) { unknown(locus, "depth-limit"); continue; }
                TypeKind kind = tm.getKind();
                if (kind.isPrimitive() || kind == TypeKind.VOID || kind == TypeKind.NONE || kind == TypeKind.NULL) {
                    continue;  // an expected terminal: no declared dependency
                }
                switch (kind) {
                    case DECLARED: {
                        DeclaredType dt = (DeclaredType) tm;
                        Element el = dt.asElement();
                        if (!(el instanceof TypeElement)) { unknown(locus, "undeclared-element"); break; }
                        String fqn = ((TypeElement) el).getQualifiedName().toString();
                        // a local or anonymous class is resolved but has no
                        // name another file could use; nothing to emit
                        if (!fqn.isEmpty()) { refs.add(fqn); }
                        for (TypeMirror arg : dt.getTypeArguments()) { stack.push(new Object[] {arg, depth + 1}); }
                        TypeMirror owner = dt.getEnclosingType();
                        if (owner != null && owner.getKind() != TypeKind.NONE) { stack.push(new Object[] {owner, depth + 1}); }
                        break;
                    }
                    case ERROR: {
                        // an error spelling is not a resolved name: record it,
                        // keep whatever its arguments still establish
                        String spelled = tm.toString();
                        unknown(locus, "unresolved " + (spelled.length() > 120 ? spelled.substring(0, 120) : spelled));
                        if (tm instanceof DeclaredType) {
                            for (TypeMirror arg : ((DeclaredType) tm).getTypeArguments()) { stack.push(new Object[] {arg, depth + 1}); }
                        }
                        break;
                    }
                    case ARRAY:
                        stack.push(new Object[] {((ArrayType) tm).getComponentType(), depth + 1});
                        break;
                    case WILDCARD: {
                        WildcardType wt = (WildcardType) tm;
                        stack.push(new Object[] {wt.getExtendsBound(), depth + 1});
                        stack.push(new Object[] {wt.getSuperBound(), depth + 1});
                        break;
                    }
                    case TYPEVAR: {
                        List<Object> key = typeVariableKey((TypeVariable) tm);
                        if (key == null) { unknown(locus, "unidentified-type-variable " + tm); break; }
                        if (!expanded.add(key)) { break; }  // a back-edge or an already-read bound: done
                        stack.push(new Object[] {((TypeVariable) tm).getUpperBound(), depth + 1});
                        stack.push(new Object[] {((TypeVariable) tm).getLowerBound(), depth + 1});
                        break;
                    }
                    case INTERSECTION:
                        for (TypeMirror b : ((IntersectionType) tm).getBounds()) { stack.push(new Object[] {b, depth + 1}); }
                        break;
                    case UNION:
                        for (TypeMirror b : ((UnionType) tm).getAlternatives()) { stack.push(new Object[] {b, depth + 1}); }
                        break;
                    default:
                        unknown(locus, "unsupported-kind " + kind);
                }
            }
        }

        /** (the declaration that binds this variable, its position there), or
         *  null when that cannot be stated -- e.g. a captured variable. */
        private static List<Object> typeVariableKey(TypeVariable tv) {
            try {
                Element e = tv.asElement();
                if (!(e instanceof TypeParameterElement)) { return null; }
                Element generic = ((TypeParameterElement) e).getGenericElement();
                if (!(generic instanceof Parameterizable)) { return null; }
                int index = ((Parameterizable) generic).getTypeParameters().indexOf(e);
                return index < 0 ? null : Arrays.asList(generic, index);
            } catch (RuntimeException unidentified) {
                return null;
            }
        }
    }

    private static boolean collectImplicitTypeNames(JavacTask task, TypeMirror start,
                                                    java.util.Set<String> names, java.util.Set<String> visiting,
                                                    java.util.Set<String> resolved) {
        if (start == null || start.getKind() != TypeKind.DECLARED) { return false; }
        Element el = task.getTypes().asElement(start);
        if (!(el instanceof TypeElement)) { return false; }
        TypeElement type = (TypeElement) el;
        String fqn = type.getQualifiedName().toString();
        // Local/anonymous types and erroneous/cyclic ancestry stay unknown.
        if (fqn.isEmpty()) { return false; }
        if (resolved.contains(fqn)) { return true; }
        if (!visiting.add(fqn)) { return false; }
        names.add(fqn);
        for (Element member : type.getEnclosedElements()) {
            if (member instanceof TypeElement) {
                names.add(((TypeElement) member).getQualifiedName().toString());
            }
        }
        try {
            for (TypeMirror parent : task.getTypes().directSupertypes(start)) {
                if (!collectImplicitTypeNames(task, parent, names, visiting, resolved)) { return false; }
            }
        } catch (RuntimeException unresolved) { return false; }
        visiting.remove(fqn);
        resolved.add(fqn);
        return true;
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
