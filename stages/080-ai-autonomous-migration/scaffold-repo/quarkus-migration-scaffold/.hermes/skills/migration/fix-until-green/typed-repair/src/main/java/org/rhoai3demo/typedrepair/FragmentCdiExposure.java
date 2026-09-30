package org.rhoai3demo.typedrepair;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

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
import org.openrewrite.java.tree.TypeUtils;

/**
 * spring-data-fragment-impl/v1, CDI part: the fragment implementation
 * {@code <Fragment>Impl} in the fragment's own package carries the resolved
 * bean scope and restricts its CDI bean types to its concrete class
 * ({@code @ApplicationScoped @Typed(<Fragment>Impl.class)}), beside its
 * {@code implements <Fragment>} (worklist.FRAGMENT_IMPL_CONTRACT,
 * worklist.fragment_cdi_exposure). Both annotations are applied together.
 *
 * <p>Scan collects every cross-file fact first: the implementation's type, its
 * supertypes, its annotations as attributed types, and the resolved call target
 * of every call its bodies make, plus every project type that is assignable to
 * the fragment. The outcome is decided once, before any edit. It never touches
 * a method body, a profile annotation or an interface list, and it refuses
 * (unresolved, no edit) the v29 recursion shape: a body that calls a method
 * declared by the fragment (or by a type assignable to it, such as the Spring
 * Data repository that extends it) on anything but {@code this} -- the
 * generated repository routes that call back to this implementation.
 */
public class FragmentCdiExposure extends ScanningRecipe<FragmentCdiExposure.Facts> {

    public static final String ID = "spring-data-fragment-impl";
    public static final String OPERATION = "fragment-cdi-exposure";

    /** Bean-defining or scope annotations that conflict with the owed scope: never replaced automatically. */
    static final Set<String> CONFLICTING = Set.of(
            "jakarta.enterprise.context.RequestScoped", "jakarta.enterprise.context.SessionScoped",
            "jakarta.enterprise.context.ConversationScoped", "jakarta.enterprise.context.Dependent",
            "jakarta.inject.Singleton", "jakarta.enterprise.inject.Vetoed",
            "org.springframework.stereotype.Component", "org.springframework.stereotype.Service",
            "org.springframework.stereotype.Repository", "org.springframework.stereotype.Controller",
            "org.springframework.web.bind.annotation.RestController",
            "org.springframework.context.annotation.Configuration", "org.springframework.context.annotation.Scope");

    private final String parent;
    private final String implementation;
    private final String path;
    private final String scope;
    private final String typed;
    private final Report report;

    public FragmentCdiExposure(String parent, String implementation, String path, String scope, String typed,
                               Report report) {
        this.parent = parent;
        this.implementation = implementation;
        this.path = path;
        this.scope = scope;
        this.typed = typed;
        this.report = report;
    }

    @Override
    public String getDisplayName() {
        return "Fragment implementation CDI exposure (spring-data-fragment-impl/v1)";
    }

    @Override
    public String getDescription() {
        return "Annotate the fragment implementation with its resolved scope and @Typed to its concrete class.";
    }

    public static final class Facts {
        boolean fileSeen;
        J.ClassDeclaration impl;
        final Set<String> assignableToParent = new TreeSet<>();
        final List<String> routedBack = new ArrayList<>();
        final Set<String> unattributed = new LinkedHashSet<>();
        final Set<String> conflicting = new TreeSet<>();
        boolean hasScope;
        J.Annotation typedAnnotation;
        List<String> typedValues;
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

    @Override
    public TreeVisitor<?, ExecutionContext> getScanner(Facts acc) {
        return new JavaIsoVisitor<ExecutionContext>() {
            @Override
            public J.ClassDeclaration visitClassDeclaration(J.ClassDeclaration cd, ExecutionContext ctx) {
                JavaType.FullyQualified t = cd.getType();
                if (t != null && !(t instanceof JavaType.Unknown) && TypeUtils.isAssignableTo(parent, t)) {
                    acc.assignableToParent.add(t.getFullyQualifiedName());
                }
                J.CompilationUnit cu = getCursor().firstEnclosing(J.CompilationUnit.class);
                if (cu != null && samePath(cu.getSourcePath(), path)) {
                    acc.fileSeen = true;
                    if (t != null && implementation.equals(t.getFullyQualifiedName())) {
                        acc.impl = cd;
                        examine(cd, acc);
                    }
                }
                return super.visitClassDeclaration(cd, ctx);
            }
        };
    }

    static boolean samePath(Path p, String want) {
        return p != null && p.normalize().toString().replace('\\', '/').equals(want);
    }

    private void examine(J.ClassDeclaration cd, Facts acc) {
        for (J.Annotation a : cd.getLeadingAnnotations()) {
            String f = fqn(a.getType());
            if (f == null) {
                acc.unattributed.add("annotation @" + a.getSimpleName() + " on " + implementation);
                continue;
            }
            if (f.equals(scope)) {
                acc.hasScope = true;
            } else if (CONFLICTING.contains(f)) {
                acc.conflicting.add(f);
            } else if (f.equals(typed)) {
                acc.typedAnnotation = a;
                acc.typedValues = classLiterals(a, acc);
            }
        }
        new JavaIsoVisitor<Facts>() {
            @Override
            public J.MethodInvocation visitMethodInvocation(J.MethodInvocation mi, Facts f) {
                call(mi.getSelect(), mi.getMethodType(), mi.getSimpleName(), getCursor(), f);
                return super.visitMethodInvocation(mi, f);
            }

            @Override
            public J.MemberReference visitMemberReference(J.MemberReference mr, Facts f) {
                call(mr.getContaining(), mr.getMethodType(), mr.getReference().getSimpleName(), getCursor(), f);
                return super.visitMemberReference(mr, f);
            }
        }.visit(cd.getBody(), acc);
    }

    private void call(Expression receiver, JavaType.Method mt, String name, Cursor c, Facts acc) {
        J.MethodDeclaration in = c.firstEnclosing(J.MethodDeclaration.class);
        String where = in == null ? "(initializer)" : in.getSimpleName();
        if (mt == null || mt.getDeclaringType() == null || fqn(mt.getDeclaringType()) == null) {
            acc.unattributed.add("the call " + name + "(...) in " + where);
            return;
        }
        if (receiver == null || (receiver instanceof J.Identifier
                && ("this".equals(((J.Identifier) receiver).getSimpleName())
                    || "super".equals(((J.Identifier) receiver).getSimpleName())))) {
            return;
        }
        String declaring = fqn(mt.getDeclaringType());
        String recv = receiver.getType() == null ? null : fqn(receiver.getType());
        boolean back = (!implementation.equals(declaring) && TypeUtils.isAssignableTo(parent, mt.getDeclaringType()))
                || (recv != null && !implementation.equals(recv) && TypeUtils.isAssignableTo(parent, receiver.getType()));
        if (back) {
            acc.routedBack.add(where + " -> " + (recv != null ? recv : declaring) + "." + mt.getName());
        }
    }

    private List<String> classLiterals(J.Annotation a, Facts acc) {
        List<String> out = new ArrayList<>();
        if (a.getArguments() == null) {
            return out;
        }
        for (Expression e : a.getArguments()) {
            Expression v = e;
            if (e instanceof J.Assignment) {
                v = ((J.Assignment) e).getAssignment();
            }
            List<Expression> items = new ArrayList<>();
            if (v instanceof J.NewArray && ((J.NewArray) v).getInitializer() != null) {
                items.addAll(((J.NewArray) v).getInitializer());
            } else if (!(v instanceof J.Empty)) {
                items.add(v);
            }
            for (Expression i : items) {
                if (i instanceof J.Empty) {
                    continue;
                }
                if (i instanceof J.FieldAccess && "class".equals(((J.FieldAccess) i).getSimpleName())) {
                    String f = fqn(((J.FieldAccess) i).getTarget().getType());
                    if (f == null) {
                        acc.unattributed.add("the @Typed class literal " + i.printTrimmed(new Cursor(null, i)));
                    } else {
                        out.add(f);
                    }
                } else {
                    acc.unattributed.add("the @Typed argument " + i.printTrimmed(new Cursor(null, i)));
                }
            }
        }
        return out;
    }

    /** The outcome, from the collected facts only; recorded once. */
    Report.Outcome decide(Facts acc) {
        if (acc.decided) {
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        acc.decided = true;
        acc.r.matched("fragment " + parent);
        String simpleParent = parent.substring(parent.lastIndexOf('.') + 1);
        if (!implementation.equals(parent + "Impl")) {
            acc.r.reason("the implementation " + implementation + " is not the naming contract's " + simpleParent
                    + "Impl in the fragment's package (spring-data-fragment-impl/v1)");
            acc.r.decide(Report.Outcome.UNRESOLVED);
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        if (!acc.fileSeen) {
            acc.r.reason("the owed implementation " + path + " does not exist on this candidate: its member bodies are "
                    + "agent work (never synthesized); the CDI exposure applies after it is written");
            acc.r.decide(Report.Outcome.UNRESOLVED);
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        if (acc.impl == null) {
            acc.r.reason(path + " declares no type " + implementation + " the compiler attributed");
            acc.r.decide(Report.Outcome.UNRESOLVED);
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        acc.r.matched("implementation " + implementation);
        J.ClassDeclaration cd = acc.impl;
        if (cd.getKind() != J.ClassDeclaration.Kind.Type.Class
                || cd.hasModifier(J.Modifier.Type.Abstract)) {
            acc.r.reason(implementation + " is not a concrete class");
            acc.r.decide(Report.Outcome.UNRESOLVED);
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        if (!TypeUtils.isAssignableTo(parent, cd.getType())) {
            acc.r.reason(implementation + " does not implement " + parent + " (the exposure is owed on that relationship)");
            acc.r.decide(Report.Outcome.UNRESOLVED);
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        if (!acc.unattributed.isEmpty()) {
            acc.r.reason("required type facts are missing, so nothing is edited: " + String.join("; ", acc.unattributed));
            acc.r.decide(Report.Outcome.UNRESOLVED);
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        if (!acc.routedBack.isEmpty()) {
            acc.r.reason("routed-back recursion (v29): " + implementation + " calls " + String.join(", ", acc.routedBack)
                    + ", which the generated Spring Data repository that extends " + simpleParent + " routes back to "
                    + implementation.substring(implementation.lastIndexOf('.') + 1)
                    + " (StackOverflowError). The CDI exposure alone would make this shape wire; each owed member must "
                    + "carry its selected source behaviour itself (bounded agent repair), never through a repository "
                    + "that extends " + simpleParent);
            acc.r.decide(Report.Outcome.UNRESOLVED);
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        if (!acc.conflicting.isEmpty()) {
            acc.r.reason(implementation + " already carries " + String.join(", ", acc.conflicting)
                    + ": a different bean scope or stereotype is not replaced automatically");
            acc.r.decide(Report.Outcome.UNRESOLVED);
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        boolean typedOk = acc.typedAnnotation != null && acc.typedValues != null
                && acc.typedValues.equals(List.of(implementation));
        if (acc.hasScope && typedOk) {
            acc.r.reason(implementation + " is already @" + simple(scope) + " @" + simple(typed) + "("
                    + simple(implementation) + ".class)");
            acc.r.decide(Report.Outcome.ALREADY);
            report.adopt(acc.r);
            return acc.r.outcome();
        }
        if (!acc.hasScope) {
            acc.r.action("add @" + scope);
        }
        if (acc.typedAnnotation != null && !typedOk) {
            acc.r.action("replace @" + simple(typed) + "(" + String.join(", ", acc.typedValues) + ") with @" + simple(typed)
                    + "(" + simple(implementation) + ".class)");
        } else if (acc.typedAnnotation == null) {
            acc.r.action("add @" + typed + "(" + simple(implementation) + ".class)");
        }
        acc.r.decide(Report.Outcome.APPLIED);
        report.adopt(acc.r);
        return acc.r.outcome();
    }

    static String simple(String fqn) {
        return fqn.substring(fqn.lastIndexOf('.') + 1);
    }

    private static final String[] STUBS = {
        "package jakarta.enterprise.context; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) "
            + "public @interface ApplicationScoped {}",
        "package jakarta.enterprise.inject; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) "
            + "public @interface Typed { Class<?>[] value() default {}; }",
    };

    private static int order(J.Annotation a, String scope, String typed) {
        String f = fqn(a.getType());
        return scope.equals(f) ? 0 : typed.equals(f) ? 1 : 2;
    }

    @Override
    public TreeVisitor<?, ExecutionContext> getVisitor(Facts acc) {
        if (decide(acc) != Report.Outcome.APPLIED) {
            return TreeVisitor.noop();
        }
        return new JavaIsoVisitor<ExecutionContext>() {
            @Override
            public J.ClassDeclaration visitClassDeclaration(J.ClassDeclaration cd, ExecutionContext ctx) {
                J.ClassDeclaration c = super.visitClassDeclaration(cd, ctx);
                if (c.getType() == null || !implementation.equals(c.getType().getFullyQualifiedName())) {
                    return c;
                }
                J.CompilationUnit cu = getCursor().firstEnclosing(J.CompilationUnit.class);
                if (cu == null || !samePath(cu.getSourcePath(), path)) {
                    return c;
                }
                Comparator<J.Annotation> byOrder = Comparator.comparingInt(a -> order(a, scope, typed));
                if (acc.typedAnnotation != null && !(acc.typedValues != null
                        && acc.typedValues.equals(List.of(implementation)))) {
                    Tree drop = acc.typedAnnotation;
                    List<J.Annotation> kept = new ArrayList<>();
                    for (J.Annotation a : c.getLeadingAnnotations()) {
                        if (!a.getId().equals(drop.getId())) {
                            kept.add(a);
                        }
                    }
                    if (!kept.isEmpty() && !c.getLeadingAnnotations().isEmpty()
                            && c.getLeadingAnnotations().get(0).getId().equals(drop.getId())) {
                        kept.set(0, kept.get(0).withPrefix(c.getLeadingAnnotations().get(0).getPrefix()));
                    }
                    c = c.withLeadingAnnotations(kept);
                    if (kept.isEmpty()) {
                        c = fixFirstModifier(c, acc.typedAnnotation);
                    }
                    acc.typedAnnotation = null;
                }
                JavaParser.Builder<?, ?> parser = JavaParser.fromJavaVersion().dependsOn(STUBS);
                boolean needScope = !acc.hasScope;
                if (needScope) {
                    c = JavaTemplate.builder("@ApplicationScoped").imports(scope).javaParser(parser).build()
                            .apply(new Cursor(getCursor().getParent(), c), c.getCoordinates().addAnnotation(byOrder));
                    maybeAddImport(scope);
                }
                c = JavaTemplate.builder("@Typed(" + simple(implementation) + ".class)").imports(typed).javaParser(parser)
                        .build().apply(new Cursor(getCursor().getParent(), c), c.getCoordinates().addAnnotation(byOrder));
                maybeAddImport(typed);
                // the class literal names this very class: give it the class's own type (the template parsed it alone)
                c = c.withLeadingAnnotations(ListUtils.map(c.getLeadingAnnotations(), a -> typedLiteral(a, cd.getType())));
                return c;
            }
        };
    }

    private J.Annotation typedLiteral(J.Annotation a, JavaType.FullyQualified self) {
        if (!typed.equals(fqn(a.getType())) || a.getArguments() == null) {
            return a;
        }
        return a.withArguments(ListUtils.map(a.getArguments(), e -> {
            if (e instanceof J.FieldAccess && ((J.FieldAccess) e).getTarget() instanceof J.Identifier) {
                J.FieldAccess fa = (J.FieldAccess) e;
                J.Identifier id = (J.Identifier) fa.getTarget();
                if (id.getSimpleName().equals(simple(implementation))) {
                    return fa.withTarget(id.withType(self));
                }
            }
            return e;
        }));
    }

    private static J.ClassDeclaration fixFirstModifier(J.ClassDeclaration c, J.Annotation removed) {
        if (!c.getModifiers().isEmpty()) {
            J.Modifier m = c.getModifiers().get(0);
            return c.withModifiers(ListUtils.map(c.getModifiers(), x -> x == m ? x.withPrefix(removed.getPrefix()) : x));
        }
        return c;
    }
}
