package org.rhoai3demo.typedrepair;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import org.openrewrite.Cursor;
import org.openrewrite.ExecutionContext;
import org.openrewrite.ScanningRecipe;
import org.openrewrite.Tree;
import org.openrewrite.TreeVisitor;
import org.openrewrite.internal.ListUtils;
import org.openrewrite.java.JavaIsoVisitor;
import org.openrewrite.java.JavaParser;
import org.openrewrite.java.JavaTemplate;
import org.openrewrite.java.tree.Expression;
import org.openrewrite.java.tree.J;
import org.openrewrite.java.tree.JavaType;
import org.openrewrite.java.tree.Space;
import org.openrewrite.java.tree.Statement;
import org.openrewrite.java.tree.TypeUtils;
import org.openrewrite.marker.Markers;

/**
 * handler-uri-parameter/v1: an HTTP handler's
 * {@code org.springframework.web.util.UriComponentsBuilder} parameter becomes
 * {@code @Context jakarta.ws.rs.core.UriInfo uriInfo}, and each of its builder
 * uses {@code <p>.path(<template>)...buildAndExpand(<args>).toUri()} becomes
 * {@code uriInfo.getBaseUriBuilder().path(<template>)....build(<args>)} in the
 * same edit (compat-mapping handler_parameters UriComponentsBuilder action and
 * location_translation). The source's path templates and argument expressions
 * are kept verbatim and in order; every argument that is not a non-null literal
 * is passed null-tolerantly as {@code Objects.toString(<arg>, "")} because Spring
 * expands a null as an empty segment and JAX-RS throws for it. No entity
 * identifier is ever substituted.
 *
 * <p>Every use of the parameter must be one of those chains, resolved by the
 * compiler to the Spring builder API; any other use, a missing type fact, or a
 * name conflict leaves the whole request unresolved and nothing is edited.
 */
public class HandlerUriParameter extends ScanningRecipe<HandlerUriParameter.Facts> {

    public static final String ID = "handler-uri-parameter";
    public static final String OPERATION = "handler-uri-parameter";
    static final String FROM = "org.springframework.web.util.UriComponentsBuilder";
    static final String SPRING_URI_BUILDER = "org.springframework.web.util.UriBuilder";
    static final String SPRING_URI_COMPONENTS = "org.springframework.web.util.UriComponents";
    static final String URI_INFO = "jakarta.ws.rs.core.UriInfo";
    static final String CONTEXT = "jakarta.ws.rs.core.Context";
    static final String OBJECTS = "java.util.Objects";
    static final String NAME = "uriInfo";

    /** One sealed handler site: the file, the declaring type, the handler, the parameter. */
    public static final class Site {
        final String path;
        final String type;
        final String member;
        final String parameter;

        public Site(String path, String type, String member, String parameter) {
            this.path = path;
            this.type = type;
            this.member = member;
            this.parameter = parameter;
        }

        String label() {
            return FragmentCdiExposure.simple(type) + "." + member + "(" + parameter + ")";
        }
    }

    private final List<Site> sites;
    private final Report report;

    public HandlerUriParameter(List<Site> sites, Report report) {
        this.sites = sites;
        this.report = report;
    }

    @Override
    public String getDisplayName() {
        return "Handler URI parameter translation (handler-uri-parameter/v1)";
    }

    @Override
    public String getDescription() {
        return "Replace a handler's UriComponentsBuilder with @Context UriInfo and translate its Location builds.";
    }

    /** A recognized builder chain ending in toUri(). */
    static final class Chain {
        UUID toUri;
        List<Expression> templates = new ArrayList<>();
        List<Expression> args = new ArrayList<>();
    }

    public static final class Facts {
        final Map<Site, String> state = new HashMap<>();          // "apply" | "already" | unresolved reason
        final Set<UUID> methods = new HashSet<>();                 // handler declarations to edit
        final Map<UUID, UUID> parameter = new HashMap<>();         // method id -> parameter declaration id
        final Map<UUID, Chain> chains = new HashMap<>();            // toUri() id -> chain
        final Set<String> seen = new LinkedHashSet<>();
        boolean decided;
        final Report r = new Report();
    }

    @Override
    public Facts getInitialValue(ExecutionContext ctx) {
        return new Facts();
    }

    private static String fqn(JavaType t) {
        JavaType.FullyQualified f = TypeUtils.asFullyQualified(t);
        return f == null || f instanceof JavaType.Unknown ? null : f.getFullyQualifiedName();
    }

    private Site siteFor(J.CompilationUnit cu, J.ClassDeclaration cd, J.MethodDeclaration md) {
        if (cu == null || cd == null || cd.getType() == null) {
            return null;
        }
        for (Site s : sites) {
            if (FragmentCdiExposure.samePath(cu.getSourcePath(), s.path) && s.type.equals(cd.getType().getFullyQualifiedName())
                    && s.member.equals(md.getSimpleName())) {
                return s;
            }
        }
        return null;
    }

    @Override
    public TreeVisitor<?, ExecutionContext> getScanner(Facts acc) {
        return new JavaIsoVisitor<ExecutionContext>() {
            @Override
            public J.MethodDeclaration visitMethodDeclaration(J.MethodDeclaration md, ExecutionContext ctx) {
                J.CompilationUnit cu = getCursor().firstEnclosing(J.CompilationUnit.class);
                J.ClassDeclaration cd = getCursor().firstEnclosing(J.ClassDeclaration.class);
                Site s = siteFor(cu, cd, md);
                if (s != null) {
                    acc.seen.add(s.label());
                    String st = examine(cu, md, s, acc);
                    String prev = acc.state.get(s);
                    // overloads of the same name: any unresolved one wins; one that applies beats "already"
                    if (prev == null || "already".equals(prev) || ("apply".equals(prev) && !"already".equals(st))) {
                        acc.state.put(s, st);
                    }
                }
                return super.visitMethodDeclaration(md, ctx);
            }
        };
    }

    private String examine(J.CompilationUnit cu, J.MethodDeclaration md, Site s, Facts acc) {
        J.VariableDeclarations param = null;
        boolean hasUriInfo = false;
        boolean nameTaken = false;
        for (Statement p : md.getParameters()) {
            if (!(p instanceof J.VariableDeclarations)) {
                continue;
            }
            J.VariableDeclarations vd = (J.VariableDeclarations) p;
            for (J.VariableDeclarations.NamedVariable v : vd.getVariables()) {
                if (v.getSimpleName().equals(s.parameter)) {
                    param = vd;
                } else if (v.getSimpleName().equals(NAME)) {
                    nameTaken = true;
                }
            }
            if (URI_INFO.equals(fqn(vd.getType()))) {
                hasUriInfo = true;
            }
        }
        if (param != null && nameTaken) {
            return "the handler " + s.label() + " already has a parameter named " + NAME;
        }
        if (param == null) {
            if (hasUriInfo) {
                return "already";
            }
            return "the handler " + s.label() + " has no parameter " + s.parameter;
        }
        String ptype = fqn(param.getType());
        if (ptype == null) {
            return "the type of " + s.label() + " is not attributed (required type fact " + FROM + " missing)";
        }
        if (!FROM.equals(ptype)) {
            return hasUriInfo && URI_INFO.equals(ptype) ? "already"
                    : "the parameter " + s.label() + " is " + ptype + ", not " + FROM;
        }
        if (hasUriInfo) {
            return "the handler " + s.label() + " already takes a UriInfo beside the builder (unsupported shape)";
        }
        if (!param.getLeadingAnnotations().isEmpty() || !param.getModifiers().isEmpty()) {
            return "the parameter " + s.label() + " carries annotations or modifiers (unsupported shape)";
        }
        for (J.Import im : cu.getImports()) {
            String simple = im.getQualid().getSimpleName();
            String full = im.getTypeName();
            if (!im.isStatic() && ((simple.equals("Context") && !full.equals(CONTEXT))
                    || (simple.equals("UriInfo") && !full.equals(URI_INFO))
                    || (simple.equals("Objects") && !full.equals(OBJECTS)))) {
                return "the file imports another " + simple + " (" + full + "): the translation's simple name would bind to it";
            }
        }
        JavaType.Variable pvar = param.getVariables().get(0).getVariableType();
        List<J.Identifier> uses = new ArrayList<>();
        List<String> problems = new ArrayList<>();
        Map<UUID, Chain> chains = new HashMap<>();
        Set<UUID> covered = new HashSet<>();
        if (md.getBody() == null) {
            return "the handler " + s.label() + " has no body";
        }
        new JavaIsoVisitor<Integer>() {
            @Override
            public J.Identifier visitIdentifier(J.Identifier id, Integer p) {
                if (id.getSimpleName().equals(NAME)) {
                    problems.add("the body already names " + NAME);
                }
                if (id.getSimpleName().equals(s.parameter)) {
                    JavaType.Variable ft = id.getFieldType();
                    J parent = getCursor().getParentTreeCursor().getValue();
                    boolean isMethodName = parent instanceof J.MethodInvocation && ((J.MethodInvocation) parent).getName() == id;
                    boolean isFieldName = parent instanceof J.FieldAccess && ((J.FieldAccess) parent).getName() == id;
                    if (!isMethodName && !isFieldName) {
                        if (ft == null) {
                            problems.add("the use of " + s.parameter + " is not attributed");
                        } else if (pvar == null || (ft.getName().equals(pvar.getName())
                                && sameOwner(ft.getOwner(), md.getMethodType()))) {
                            uses.add(id);
                        }
                    }
                }
                return super.visitIdentifier(id, p);
            }

            @Override
            public J.MethodInvocation visitMethodInvocation(J.MethodInvocation mi, Integer p) {
                Chain c = chain(mi, s.parameter, problems);
                if (c != null) {
                    chains.put(mi.getId(), c);
                    Expression e = mi;
                    while (e instanceof J.MethodInvocation) {
                        e = ((J.MethodInvocation) e).getSelect();
                    }
                    covered.add(((J.Identifier) e).getId());
                }
                return super.visitMethodInvocation(mi, p);
            }
        }.visit(md.getBody(), 0);
        if (!problems.isEmpty()) {
            return s.label() + ": " + String.join("; ", new LinkedHashSet<>(problems));
        }
        // an unused builder: the documented action is the parameter replacement alone (there is no Location)
        for (J.Identifier u : uses) {
            if (!covered.contains(u.getId())) {
                return "the handler " + s.label() + " uses " + s.parameter
                        + " outside <builder>.path(<template>).buildAndExpand(<args>).toUri() (unsupported builder use)";
            }
        }
        acc.methods.add(md.getId());
        acc.parameter.put(md.getId(), param.getId());
        acc.chains.putAll(chains);
        acc.r.matched("handler parameter " + s.type + "#" + s.member + "(" + s.parameter + ": " + FROM + ")");
        return "apply";
    }

    private static boolean sameOwner(JavaType owner, JavaType.Method method) {
        if (!(owner instanceof JavaType.Method) || method == null) {
            return false;
        }
        JavaType.Method o = (JavaType.Method) owner;
        return o.getName().equals(method.getName()) && String.valueOf(fqn(o.getDeclaringType()))
                .equals(String.valueOf(fqn(method.getDeclaringType())))
                && o.getParameterTypes().size() == method.getParameterTypes().size();
    }

    private static boolean declaredBy(J.MethodInvocation mi, String... owners) {
        JavaType.Method mt = mi.getMethodType();
        String d = mt == null ? null : fqn(mt.getDeclaringType());
        if (d == null) {
            return false;
        }
        for (String o : owners) {
            if (o.equals(d)) {
                return true;
            }
        }
        return false;
    }

    /** toUri() over buildAndExpand(args) over path(template)+ over the parameter, every call typed; else null. */
    private Chain chain(J.MethodInvocation toUri, String pname, List<String> problems) {
        if (!"toUri".equals(toUri.getSimpleName()) || !(toUri.getSelect() instanceof J.MethodInvocation)) {
            return null;
        }
        J.MethodInvocation expand = (J.MethodInvocation) toUri.getSelect();
        if (!"buildAndExpand".equals(expand.getSimpleName())) {
            return null;
        }
        List<J.MethodInvocation> paths = new ArrayList<>();
        Expression e = expand.getSelect();
        while (e instanceof J.MethodInvocation && "path".equals(((J.MethodInvocation) e).getSimpleName())) {
            paths.add(0, (J.MethodInvocation) e);
            e = ((J.MethodInvocation) e).getSelect();
        }
        if (!(e instanceof J.Identifier) || !((J.Identifier) e).getSimpleName().equals(pname) || paths.isEmpty()) {
            return null;
        }
        if (toUri.getMethodType() == null || expand.getMethodType() == null
                || paths.stream().anyMatch(p -> p.getMethodType() == null)) {
            problems.add("the builder chain is not attributed (the Spring builder API is a required type fact)");
            return null;
        }
        if (!declaredBy(toUri, SPRING_URI_COMPONENTS) || !declaredBy(expand, FROM)
                || paths.stream().anyMatch(p -> !declaredBy(p, FROM, SPRING_URI_BUILDER))) {
            problems.add("the builder chain does not resolve to " + FROM + " path/buildAndExpand and UriComponents.toUri");
            return null;
        }
        List<JavaType> ptypes = expand.getMethodType().getParameterTypes();
        if (ptypes.size() != 1 || !(ptypes.get(0) instanceof JavaType.Array)) {
            problems.add("buildAndExpand(" + (ptypes.isEmpty() ? "" : String.valueOf(ptypes.get(0)))
                    + ") is not the positional Object... form (a Map expansion is unsupported)");
            return null;
        }
        Chain c = new Chain();
        c.toUri = toUri.getId();
        for (J.MethodInvocation p : paths) {
            if (p.getArguments().size() != 1 || !TypeUtils.isString(p.getArguments().get(0).getType())) {
                problems.add("a path(...) segment is not one String template");
                return null;
            }
            c.templates.add(p.getArguments().get(0));
        }
        for (Expression a : expand.getArguments()) {
            if (!(a instanceof J.Empty)) {
                c.args.add(a);
            }
        }
        return c;
    }

    Report.Outcome decide(Facts acc) {
        if (acc.decided) {
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        acc.decided = true;
        List<String> unresolved = new ArrayList<>();
        int apply = 0;
        for (Site s : sites) {
            String st = acc.state.get(s);
            if (st == null) {
                unresolved.add("the handler " + s.label() + " was not found in " + s.path);
            } else if ("apply".equals(st)) {
                apply++;
            } else if (!"already".equals(st)) {
                unresolved.add(st);
            }
        }
        if (sites.isEmpty()) {
            acc.r.reason("no handler site was named");
            acc.r.decide(Report.Outcome.NOT_APPLICABLE);
        } else if (!unresolved.isEmpty()) {
            unresolved.forEach(acc.r::reason);
            acc.r.decide(Report.Outcome.UNRESOLVED);
        } else if (apply == 0) {
            acc.r.reason("every named handler already takes @Context UriInfo and no " + FROM);
            acc.r.decide(Report.Outcome.ALREADY);
        } else {
            for (Site s : sites) {
                if ("apply".equals(acc.state.get(s))) {
                    acc.r.action("replace " + s.label() + " with @Context UriInfo " + NAME
                            + " and translate its Location build(s)");
                }
            }
            acc.r.decide(Report.Outcome.APPLIED);
        }
        report.adopt(acc.r);
        return acc.r.outcome();
    }

    private static final String[] STUBS = {
        "package jakarta.ws.rs.core; public interface UriBuilder { UriBuilder path(String p); "
            + "java.net.URI build(Object... values); }",
        "package jakarta.ws.rs.core; public interface UriInfo { UriBuilder getBaseUriBuilder(); }",
    };

    private static J.Identifier ident(String name, JavaType type) {
        return new J.Identifier(Tree.randomId(), Space.EMPTY, Markers.EMPTY, Collections.emptyList(), name, type, null);
    }

    private static boolean nonNullLiteral(Expression a) {
        return a instanceof J.Literal && ((J.Literal) a).getValue() != null;
    }

    @Override
    public TreeVisitor<?, ExecutionContext> getVisitor(Facts acc) {
        if (decide(acc) != Report.Outcome.APPLIED) {
            return TreeVisitor.noop();
        }
        JavaType.ShallowClass uriInfoType = JavaType.ShallowClass.build(URI_INFO);
        JavaType.ShallowClass contextType = JavaType.ShallowClass.build(CONTEXT);
        return new JavaIsoVisitor<ExecutionContext>() {
            @Override
            public J.MethodDeclaration visitMethodDeclaration(J.MethodDeclaration md, ExecutionContext ctx) {
                J.MethodDeclaration m = super.visitMethodDeclaration(md, ctx);
                if (!acc.methods.contains(md.getId())) {
                    return m;
                }
                UUID pid = acc.parameter.get(md.getId());
                m = m.withParameters(ListUtils.map(m.getParameters(), p -> {
                    if (!(p instanceof J.VariableDeclarations) || !p.getId().equals(pid)) {
                        return p;
                    }
                    J.VariableDeclarations vd = (J.VariableDeclarations) p;
                    J.Annotation ctxAnn = new J.Annotation(Tree.randomId(), Space.EMPTY, Markers.EMPTY,
                            ident("Context", contextType), null);
                    J.VariableDeclarations out = vd
                            .withLeadingAnnotations(List.of(ctxAnn))
                            .withTypeExpression(ident("UriInfo", uriInfoType).withPrefix(Space.SINGLE_SPACE))
                            .withType(uriInfoType);
                    return out.withVariables(ListUtils.map(out.getVariables(), v -> {
                        JavaType.Variable vt = v.getVariableType() == null ? null
                                : v.getVariableType().withName(NAME).withType(uriInfoType);
                        return v.withName(v.getName().withSimpleName(NAME).withType(uriInfoType).withFieldType(vt))
                                .withVariableType(vt);
                    }));
                }));
                maybeAddImport(CONTEXT);
                maybeAddImport(URI_INFO);
                maybeRemoveImport(FROM);
                return m;
            }

            @Override
            public J.MethodInvocation visitMethodInvocation(J.MethodInvocation mi, ExecutionContext ctx) {
                Chain c = acc.chains.get(mi.getId());
                if (c == null) {
                    return super.visitMethodInvocation(mi, ctx);
                }
                StringBuilder t = new StringBuilder("#{any(" + URI_INFO + ")}.getBaseUriBuilder()");
                List<Object> params = new ArrayList<>();
                params.add(ident(NAME, uriInfoType));
                for (Expression tpl : c.templates) {
                    t.append(".path(#{any(java.lang.String)})");
                    params.add(tpl);
                }
                t.append(".build(");
                boolean wrapped = false;
                for (int i = 0; i < c.args.size(); i++) {
                    Expression a = c.args.get(i);
                    if (i > 0) {
                        t.append(", ");
                    }
                    if (nonNullLiteral(a)) {
                        t.append("#{any()}");
                    } else {
                        t.append("Objects.toString(#{any()}, \"\")");
                        wrapped = true;
                    }
                    params.add(a.withPrefix(Space.EMPTY));
                }
                t.append(")");
                JavaTemplate.Builder b = JavaTemplate.builder(t.toString())
                        .javaParser(JavaParser.fromJavaVersion().dependsOn(STUBS));
                if (wrapped) {
                    b = b.imports(OBJECTS);
                    maybeAddImport(OBJECTS);
                }
                return b.build().apply(new Cursor(getCursor().getParent(), mi), mi.getCoordinates().replace(),
                        params.toArray());
            }
        };
    }
}
