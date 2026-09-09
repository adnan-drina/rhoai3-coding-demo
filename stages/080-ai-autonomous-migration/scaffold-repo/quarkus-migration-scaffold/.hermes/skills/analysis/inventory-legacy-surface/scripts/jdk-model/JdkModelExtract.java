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
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.stream.Stream;

import javax.lang.model.element.AnnotationMirror;
import javax.lang.model.element.AnnotationValue;
import javax.lang.model.element.Element;
import javax.lang.model.element.ElementKind;
import javax.lang.model.element.ExecutableElement;
import javax.lang.model.element.Modifier;
import javax.lang.model.element.TypeElement;
import javax.lang.model.element.VariableElement;
import javax.lang.model.type.DeclaredType;
import javax.lang.model.type.TypeKind;
import javax.lang.model.type.TypeMirror;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

import com.sun.source.tree.AnnotationTree;
import com.sun.source.tree.AssignmentTree;
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.ExpressionTree;
import com.sun.source.tree.LiteralTree;
import com.sun.source.tree.ModifiersTree;
import com.sun.source.tree.NewArrayTree;
import com.sun.source.tree.VariableTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.IdentifierTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;

/**
 * Stage 080 structural extractor on the JDK's own compiler API
 * (javax.lang.model + com.sun.source through JavacTask). No third-party
 * dependency: the pinned toolchain JDK is the extractor. Emits
 * rhoai3.structure/v1 JSON in the same shape the normalizer consumes.
 *
 * Usage: java JdkModelExtract --source DIR --out FILE [--classpath FILE] [--release N]
 *
 * With --classpath (a Maven build-classpath file) attribution resolves
 * against the real dependencies (mode full). Without it javac attributes
 * with error types for every unresolved reference (mode partial): the
 * name is recorded as written and the claim is marked partial. The
 * extractor records claims; it decides nothing.
 */
public final class JdkModelExtract {

    private static Path sourceRoot;
    private static final Set<String> modelTypes = new TreeSet<>();
    private static Trees trees;

    public static void main(String[] args) throws IOException {
        String source = null;
        String out = null;
        String classpath = null;
        String release = "17";
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--source": source = args[++i]; break;
                case "--out": out = args[++i]; break;
                case "--classpath": classpath = args[++i]; break;
                case "--release": release = args[++i]; break;
                default:
                    System.err.println("unknown arg " + args[i]);
                    System.exit(2);
            }
        }
        if (source == null || out == null) {
            System.err.println("usage: JdkModelExtract --source DIR --out FILE [--classpath FILE] [--release N]");
            System.exit(2);
        }
        sourceRoot = Paths.get(source).toAbsolutePath().normalize();
        List<Path> roots = new ArrayList<>();
        for (String rel : new String[] {"src/main/java", "src/test/java"}) {
            Path p = sourceRoot.resolve(rel);
            if (Files.isDirectory(p)) roots.add(p);
        }
        if (roots.isEmpty()) roots.add(sourceRoot);
        List<Path> javaFiles = new ArrayList<>();
        for (Path r : roots) {
            try (Stream<Path> s = Files.walk(r)) {
                s.filter(p -> p.toString().endsWith(".java") && Files.isRegularFile(p))
                 .filter(p -> !p.getFileName().toString().equals("module-info.java"))
                 .forEach(javaFiles::add);
            }
        }
        javaFiles.sort(null);

        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            System.err.println("FAIL: no system Java compiler (a JRE, not a JDK)");
            System.exit(1);
        }
        DiagnosticCollector<JavaFileObject> diags = new DiagnosticCollector<>();
        StandardJavaFileManager fm = compiler.getStandardFileManager(diags, null, StandardCharsets.UTF_8);
        List<String> options = new ArrayList<>();
        options.add("-proc:none");
        options.add("-Xlint:none");
        options.add("-implicit:none");
        options.add("-XDshould-stop.ifError=FLOW");
        options.add("-XDshould-stop.ifNoError=FLOW");
        options.add("--release");
        options.add(release);
        String mode = "partial";
        if (classpath != null && Files.isRegularFile(Paths.get(classpath))) {
            String cp = new String(Files.readAllBytes(Paths.get(classpath)), StandardCharsets.UTF_8).trim();
            List<String> entries = new ArrayList<>();
            for (String e : cp.split(java.io.File.pathSeparator)) {
                if (!e.isEmpty()) entries.add(e);
            }
            Path classes = sourceRoot.resolve("target/classes");
            if (Files.isDirectory(classes)) entries.add(classes.toString());
            options.add("-classpath");
            options.add(String.join(java.io.File.pathSeparator, entries));
            mode = "full";
        }
        Path scratch = Files.createTempDirectory("jdk-model-classes");
        options.add("-d");
        options.add(scratch.toString());
        Iterable<? extends JavaFileObject> units = fm.getJavaFileObjectsFromPaths(javaFiles);
        JavacTask task = (JavacTask) compiler.getTask(null, fm, diags, options, null, units);
        trees = Trees.instance(task);
        Iterable<? extends CompilationUnitTree> cus = task.parse();
        task.analyze();

        List<Map.Entry<TypeElement, TreePath>> found = new ArrayList<>();
        for (CompilationUnitTree cu : cus) {
            new TreePathScanner<Void, Void>() {
                @Override public Void visitClass(ClassTree node, Void v) {
                    Element el = trees.getElement(getCurrentPath());
                    if (el instanceof TypeElement) {
                        TypeElement te = (TypeElement) el;
                        if (te.getQualifiedName().length() > 0) {
                            modelTypes.add(te.getQualifiedName().toString());
                            found.add(Map.entry(te, getCurrentPath()));
                        }
                    }
                    return super.visitClass(node, v);
                }
            }.scan(cu, null);
        }
        found.sort((a, b) -> a.getKey().getQualifiedName().toString().compareTo(b.getKey().getQualifiedName().toString()));

        Map<String, Object> doc = new LinkedHashMap<>();
        doc.put("schema", "rhoai3.structure/v1");
        Map<String, Object> producer = new LinkedHashMap<>();
        producer.put("tool", "jdk-model");
        producer.put("version", "jdk-" + Runtime.version().feature());
        producer.put("runtime", System.getProperty("java.vendor", "") + " " + System.getProperty("java.runtime.version", ""));
        producer.put("mode", mode);
        doc.put("producer", producer);
        doc.put("source_digest", "");
        doc.put("mode", mode);
        List<Object> typeDocs = new ArrayList<>();
        for (Map.Entry<TypeElement, TreePath> e : found) {
            typeDocs.add(typeDoc(e.getKey(), e.getValue(), mode));
        }
        doc.put("types", typeDocs);
        try (Writer w = Files.newBufferedWriter(Paths.get(out), StandardCharsets.UTF_8)) {
            Json.write(w, doc);
            w.write("\n");
        }
        System.err.println("OK: jdk-model extract " + typeDocs.size() + " types mode=" + mode + " files=" + javaFiles.size());
    }

    private static String relPath(TreePath path) {
        CompilationUnitTree cu = path.getCompilationUnit();
        if (cu == null || cu.getSourceFile() == null) return "";
        Path p = Paths.get(cu.getSourceFile().toUri()).toAbsolutePath().normalize();
        try {
            return sourceRoot.relativize(p).toString().replace('\\', '/');
        } catch (IllegalArgumentException ex) {
            return p.toString();
        }
    }

    private static String kindOf(TypeElement t) {
        switch (t.getKind()) {
            case ANNOTATION_TYPE: return "annotation";
            case ENUM: return "enum";
            case INTERFACE: return "interface";
            case RECORD: return "record";
            default: return "class";
        }
    }

    /** Qualified name of a type mirror as the normalizer expects it; error types keep the name as written. */
    private static String nameOf(TypeMirror tm) {
        if (tm == null) return "";
        switch (tm.getKind()) {
            case DECLARED: {
                Element el = ((DeclaredType) tm).asElement();
                if (el instanceof TypeElement) return ((TypeElement) el).getQualifiedName().toString();
                return tm.toString();
            }
            case ARRAY:
            case TYPEVAR:
            case WILDCARD:
            case ERROR:
            default: {
                String s = tm.toString();
                int lt = s.indexOf('<');
                return lt >= 0 ? s.substring(0, lt) : s;
            }
        }
    }

    private static boolean resolved(TypeMirror tm) {
        if (tm == null) return true;
        if (tm.getKind() == TypeKind.ERROR) return false;
        if (tm.getKind() == TypeKind.DECLARED) {
            for (TypeMirror a : ((DeclaredType) tm).getTypeArguments()) {
                if (!resolved(a)) return false;
            }
        }
        return true;
    }

    /** Erased declared-type names referenced by a mirror (generics walked, primitives skipped). */
    private static void collectRefs(TypeMirror tm, Set<String> into, boolean[] partial) {
        if (tm == null) return;
        switch (tm.getKind()) {
            case DECLARED: {
                DeclaredType dt = (DeclaredType) tm;
                into.add(nameOf(dt));
                for (TypeMirror a : dt.getTypeArguments()) collectRefs(a, into, partial);
                return;
            }
            case ARRAY:
                collectRefs(((javax.lang.model.type.ArrayType) tm).getComponentType(), into, partial);
                return;
            case ERROR:
                into.add(nameOf(tm));
                partial[0] = true;
                return;
            case WILDCARD: {
                javax.lang.model.type.WildcardType wt = (javax.lang.model.type.WildcardType) tm;
                collectRefs(wt.getExtendsBound(), into, partial);
                collectRefs(wt.getSuperBound(), into, partial);
                return;
            }
            default:
                return;
        }
    }

    private static Map<String, Object> typeDoc(TypeElement t, TreePath path, String mode) {
        Map<String, Object> d = new LinkedHashMap<>();
        d.put("fqn", t.getQualifiedName().toString());
        d.put("path", relPath(path));
        d.put("kind", kindOf(t));
        List<Object> mods = new ArrayList<>();
        for (Modifier m : new TreeSet<>(t.getModifiers())) mods.add(m.toString().toLowerCase());
        d.put("modifiers", mods);
        List<Object> imports = new ArrayList<>();
        Set<String> imp = new TreeSet<>();
        for (ImportTree it : path.getCompilationUnit().getImports()) {
            imp.add(it.getQualifiedIdentifier().toString());
        }
        imports.addAll(imp);
        d.put("imports", imports);
        boolean[] partial = {mode.equals("partial")};
        ClassTree ct = (ClassTree) path.getLeaf();
        d.put("annotations", annotationsFromTree(ct.getModifiers(), path));
        Set<String> supers = new TreeSet<>();
        TypeMirror sc = t.getSuperclass();
        if (sc != null && sc.getKind() != TypeKind.NONE) {
            String n = nameOf(sc);
            if (!n.equals("java.lang.Object")) supers.add(n);
            if (!resolved(sc)) partial[0] = true;
        }
        for (TypeMirror i : t.getInterfaces()) {
            supers.add(nameOf(i));
            if (!resolved(i)) partial[0] = true;
        }
        d.put("supertypes", new ArrayList<>(supers));
        Set<String> typeRefs = new TreeSet<>();
        List<Object> fields = new ArrayList<>();
        List<Object> ctors = new ArrayList<>();
        List<Object> methods = new ArrayList<>();
        for (Element member : t.getEnclosedElements()) {
            if (member.getKind() == ElementKind.FIELD || member.getKind() == ElementKind.ENUM_CONSTANT) {
                VariableElement f = (VariableElement) member;
                Map<String, Object> fd = new LinkedHashMap<>();
                fd.put("name", f.getSimpleName().toString());
                fd.put("type", nameOf(f.asType()));
                fd.put("annotations", memberAnnotations(f));
                collectRefs(f.asType(), typeRefs, partial);
                fields.add(fd);
            } else if (member.getKind() == ElementKind.CONSTRUCTOR) {
                ExecutableElement c = (ExecutableElement) member;
                if (c.getParameters().isEmpty() && trees.getTree(c) == null) continue; // implicit
                Map<String, Object> cd = new LinkedHashMap<>();
                cd.put("params", params(c.getParameters(), typeRefs, partial));
                cd.put("annotations", memberAnnotations(c));
                ctors.add(cd);
            } else if (member.getKind() == ElementKind.METHOD) {
                ExecutableElement m = (ExecutableElement) member;
                Map<String, Object> md = new LinkedHashMap<>();
                md.put("name", m.getSimpleName().toString());
                md.put("signature", signature(m));
                md.put("annotations", memberAnnotations(m));
                Set<String> mrefs = new TreeSet<>();
                boolean[] mpartial = {false};
                md.put("params", params(m.getParameters(), mrefs, mpartial));
                md.put("returns", m.getReturnType().getKind() == TypeKind.VOID ? "void" : nameOf(m.getReturnType()));
                collectRefs(m.getReturnType(), mrefs, mpartial);
                List<Object> calls = new ArrayList<>();
                MethodTree mt = trees.getTree(m);
                if (mt != null && mt.getBody() != null) {
                    TreePath mpath = trees.getPath(m);
                    Set<String> seen = new TreeSet<>();
                    new TreePathScanner<Void, Void>() {
                        @Override public Void visitMethodInvocation(MethodInvocationTree node, Void v) {
                            Element el = trees.getElement(new TreePath(getCurrentPath(), node.getMethodSelect()));
                            if (el instanceof ExecutableElement) {
                                Element owner = el.getEnclosingElement();
                                String o = owner instanceof TypeElement ? ((TypeElement) owner).getQualifiedName().toString() : "";
                                String n = el.getSimpleName().toString();
                                if (!o.isEmpty() && seen.add(o + "#" + n)) {
                                    Map<String, Object> cd = new LinkedHashMap<>();
                                    cd.put("owner", o);
                                    cd.put("name", n);
                                    calls.add(cd);
                                    mrefs.add(o);
                                }
                            } else {
                                mpartial[0] = true; // unresolved call target
                            }
                            return super.visitMethodInvocation(node, v);
                        }
                        // Body references: only resolved declared types are claims; an
                        // error-typed name inside a body marks the method partial without
                        // inventing a reference (the name would be a library type anyway).
                        @Override public Void visitIdentifier(IdentifierTree node, Void v) {
                            TypeMirror tm = trees.getTypeMirror(getCurrentPath());
                            if (tm != null && tm.getKind() == TypeKind.DECLARED) collectRefs(tm, mrefs, mpartial);
                            else if (tm != null && tm.getKind() == TypeKind.ERROR) mpartial[0] = true;
                            return super.visitIdentifier(node, v);
                        }
                        @Override public Void visitMemberSelect(MemberSelectTree node, Void v) {
                            TypeMirror tm = trees.getTypeMirror(getCurrentPath());
                            if (tm != null && tm.getKind() == TypeKind.DECLARED) collectRefs(tm, mrefs, mpartial);
                            else if (tm != null && tm.getKind() == TypeKind.ERROR) mpartial[0] = true;
                            return super.visitMemberSelect(node, v);
                        }
                    }.scan(mpath, null);
                }
                mrefs.remove(t.getQualifiedName().toString());
                md.put("type_refs", new ArrayList<>(mrefs));
                md.put("calls", calls);
                md.put("resolution", (partial[0] || mpartial[0]) ? "partial" : "full");
                if (mpartial[0]) partial[0] = true;
                typeRefs.addAll(mrefs);
                methods.add(md);
            }
        }
        methods.sort((a, b) -> String.valueOf(((Map<?, ?>) a).get("signature")).compareTo(String.valueOf(((Map<?, ?>) b).get("signature"))));
        d.put("fields", fields);
        d.put("constructors", ctors);
        d.put("methods", methods);
        for (AnnotationMirror am : t.getAnnotationMirrors()) {
            if (!resolved(am.getAnnotationType())) partial[0] = true;
        }
        Set<String> appRefs = new TreeSet<>();
        for (String r : typeRefs) {
            if (r.equals(t.getQualifiedName().toString())) continue;
            if (modelTypes.contains(r)) appRefs.add(r);
        }
        d.put("type_refs", new ArrayList<>(appRefs));
        d.put("resolution", partial[0] ? "partial" : "full");
        return d;
    }

    private static String signature(ExecutableElement m) {
        StringBuilder sb = new StringBuilder(m.getSimpleName()).append('(');
        boolean first = true;
        for (VariableElement p : m.getParameters()) {
            if (!first) sb.append(',');
            first = false;
            sb.append(nameOf(p.asType()));
        }
        return sb.append(')').toString();
    }

    private static List<Object> params(List<? extends VariableElement> ps, Set<String> refs, boolean[] partial) {
        List<Object> out = new ArrayList<>();
        for (VariableElement p : ps) {
            Map<String, Object> pd = new LinkedHashMap<>();
            pd.put("name", p.getSimpleName().toString());
            pd.put("type", nameOf(p.asType()));
            pd.put("annotations", memberAnnotations(p));
            collectRefs(p.asType(), refs, partial);
            out.add(pd);
        }
        return out;
    }

    /** Annotations of a member from its declaration tree; falls back to the mirrors when no tree exists. */
    private static List<Object> memberAnnotations(Element el) {
        TreePath tp = trees.getPath(el);
        Tree leaf = tp == null ? null : tp.getLeaf();
        ModifiersTree mods = null;
        if (leaf instanceof MethodTree) mods = ((MethodTree) leaf).getModifiers();
        else if (leaf instanceof VariableTree) mods = ((VariableTree) leaf).getModifiers();
        else if (leaf instanceof ClassTree) mods = ((ClassTree) leaf).getModifiers();
        if (mods == null || tp == null) return annotations(el.getAnnotationMirrors());
        return annotationsFromTree(mods, tp);
    }

    /**
     * Annotations read from the syntax tree. javac's element API drops the
     * attribute values of an annotation whose type could not be resolved
     * (partial mode); the tree still carries them exactly as written, which
     * is what the entry-point catalog needs (@RequestMapping("/api/owners")).
     */
    private static List<Object> annotationsFromTree(ModifiersTree mods, TreePath base) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (AnnotationTree at : mods.getAnnotations()) {
            TreePath ap = new TreePath(base, at);
            TypeMirror tm = trees.getTypeMirror(new TreePath(ap, at.getAnnotationType()));
            String fqn = tm == null ? at.getAnnotationType().toString() : nameOf(tm);
            if (fqn.isEmpty() || fqn.startsWith("<")) fqn = at.getAnnotationType().toString();
            Map<String, Object> ad = new LinkedHashMap<>();
            ad.put("fqn", fqn);
            Map<String, Object> values = new TreeMap<>();
            for (ExpressionTree arg : at.getArguments()) {
                if (arg instanceof AssignmentTree) {
                    AssignmentTree as = (AssignmentTree) arg;
                    values.put(as.getVariable().toString(), treeValues(as.getExpression()));
                } else {
                    values.put("value", treeValues(arg));
                }
            }
            ad.put("values", values);
            out.add(ad);
        }
        out.sort((a, b) -> String.valueOf(a.get("fqn")).compareTo(String.valueOf(b.get("fqn"))));
        return new ArrayList<>(out);
    }

    private static List<Object> treeValues(ExpressionTree e) {
        List<Object> out = new ArrayList<>();
        if (e instanceof NewArrayTree) {
            for (ExpressionTree el : ((NewArrayTree) e).getInitializers()) out.addAll(treeValues(el));
            return out;
        }
        if (e instanceof LiteralTree) {
            Object v = ((LiteralTree) e).getValue();
            out.add(v == null ? "null" : String.valueOf(v));
            return out;
        }
        String s = e.toString();
        int dot = s.lastIndexOf('.');
        out.add(dot >= 0 && s.indexOf('(') < 0 ? s.substring(dot + 1) : s);
        return out;
    }

    private static List<Object> annotations(List<? extends AnnotationMirror> anns) {
        List<Object> out = new ArrayList<>();
        List<AnnotationMirror> sorted = new ArrayList<>(anns);
        sorted.sort((a, b) -> nameOf(a.getAnnotationType()).compareTo(nameOf(b.getAnnotationType())));
        for (AnnotationMirror a : sorted) {
            Map<String, Object> ad = new LinkedHashMap<>();
            ad.put("fqn", nameOf(a.getAnnotationType()));
            Map<String, Object> values = new TreeMap<>();
            for (Map.Entry<? extends ExecutableElement, ? extends AnnotationValue> e : a.getElementValues().entrySet()) {
                values.put(e.getKey().getSimpleName().toString(), annValues(e.getValue()));
            }
            ad.put("values", values);
            out.add(ad);
        }
        return out;
    }

    private static List<Object> annValues(AnnotationValue av) {
        List<Object> out = new ArrayList<>();
        Object v = av.getValue();
        if (v instanceof List) {
            for (Object el : (List<?>) v) {
                if (el instanceof AnnotationValue) out.addAll(annValues((AnnotationValue) el));
                else out.add(String.valueOf(el));
            }
            return out;
        }
        if (v instanceof VariableElement) { // enum constant
            out.add(((VariableElement) v).getSimpleName().toString());
            return out;
        }
        if (v instanceof TypeMirror) {
            out.add(nameOf((TypeMirror) v));
            return out;
        }
        if (v instanceof AnnotationMirror) {
            out.add(nameOf(((AnnotationMirror) v).getAnnotationType()));
            return out;
        }
        String s = String.valueOf(v);
        if (s.startsWith("<error") || s.contains("error")) {
            // javac could not evaluate the constant (unresolved reference); keep the raw text
            String raw = av.toString();
            out.add(raw.length() > 1 && raw.startsWith("\"") && raw.endsWith("\"") ? raw.substring(1, raw.length() - 1) : raw);
            return out;
        }
        out.add(s);
        return out;
    }

    /** Minimal JSON writer (the extractor has no dependencies). */
    static final class Json {
        static void write(Writer w, Object o) throws IOException {
            if (o == null) { w.write("null"); return; }
            if (o instanceof String) { str(w, (String) o); return; }
            if (o instanceof Number || o instanceof Boolean) { w.write(o.toString()); return; }
            if (o instanceof Map) {
                w.write("{");
                boolean first = true;
                for (Map.Entry<?, ?> e : ((Map<?, ?>) o).entrySet()) {
                    if (!first) w.write(",");
                    first = false;
                    str(w, String.valueOf(e.getKey()));
                    w.write(":");
                    write(w, e.getValue());
                }
                w.write("}");
                return;
            }
            if (o instanceof List) {
                w.write("[");
                boolean first = true;
                for (Object e : (List<?>) o) {
                    if (!first) w.write(",");
                    first = false;
                    write(w, e);
                }
                w.write("]");
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
                        if (c < 0x20 || c > 0x7e) w.write(String.format("\\u%04x", (int) c));
                        else w.write(c);
                }
            }
            w.write('"');
        }
    }
}
