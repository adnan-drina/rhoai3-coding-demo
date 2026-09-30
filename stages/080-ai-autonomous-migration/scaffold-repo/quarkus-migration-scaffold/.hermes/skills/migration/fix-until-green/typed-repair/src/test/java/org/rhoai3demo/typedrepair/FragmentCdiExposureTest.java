package org.rhoai3demo.typedrepair;

import static org.assertj.core.api.Assertions.assertThat;
import static org.openrewrite.java.Assertions.java;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.openrewrite.java.JavaParser;
import org.openrewrite.test.RecipeSpec;
import org.openrewrite.test.RewriteTest;
import org.openrewrite.test.SourceSpecs;

/**
 * V26-2 qualification of spring-data-fragment-impl (CDI exposure): before/after,
 * unchanged negatives, second application, unrelated same-named types, renamed
 * packages, missing type facts and the v29 routed-back recursion refused before
 * any edit.
 */
class FragmentCdiExposureTest implements RewriteTest {

    static final String SCOPE = "jakarta.enterprise.context.ApplicationScoped";
    static final String TYPED = "jakarta.enterprise.inject.Typed";

    @Override
    public void defaults(RecipeSpec spec) {
        spec.parser(JavaParser.fromJavaVersion().dependsOn(Stubs.CDI)).validateRecipeSerialization(false);
    }

    static FragmentCdiExposure recipe(String pkg, Report r) {
        return new FragmentCdiExposure(pkg + ".repository.OwnerRepository", pkg + ".repository.OwnerRepositoryImpl",
                "src/main/java/" + pkg.replace('.', '/') + "/repository/OwnerRepositoryImpl.java", SCOPE, TYPED, r);
    }

    static String p(String pkg, String rel) {
        return "src/main/java/" + pkg.replace('.', '/') + "/" + rel;
    }

    static SourceSpecs[] with(String pkg, SourceSpecs... more) {
        SourceSpecs[] base = support(pkg);
        SourceSpecs[] out = java.util.Arrays.copyOf(base, base.length + more.length);
        System.arraycopy(more, 0, out, base.length, more.length);
        return out;
    }

    static SourceSpecs[] support(String pkg) {
        return new SourceSpecs[]{java("package " + pkg + ".model; public class Owner { public Integer getId() { return null; } }",
                        s -> s.path(p(pkg, "model/Owner.java"))),
                java("package " + pkg + ".repository; import java.util.Collection; import " + pkg + ".model.Owner;\n"
                        + "public interface OwnerRepository { Owner findById(int id); Collection<Owner> findAll(); void save(Owner o); }",
                        s -> s.path(p(pkg, "repository/OwnerRepository.java"))),
                java("package " + pkg + ".repository.springdatajpa; import " + pkg + ".model.Owner; import " + pkg
                        + ".repository.OwnerRepository; import org.springframework.data.repository.Repository;\n"
                        + "public interface SpringDataOwnerRepository extends OwnerRepository, Repository<Owner, Integer> {}",
                        s -> s.path(p(pkg, "repository/springdatajpa/SpringDataOwnerRepository.java")))};
    }

    static String implBody(String pkg) {
        return "public class OwnerRepositoryImpl implements OwnerRepository {\n\n"
                + "    private EntityManager em;\n\n"
                + "    @Override\n"
                + "    public Owner findById(int id) {\n"
                + "        return this.em.find(Owner.class, id);\n"
                + "    }\n\n"
                + "    @Override\n"
                + "    public Collection<Owner> findAll() {\n"
                + "        return java.util.List.of();\n"
                + "    }\n\n"
                + "    @Override\n"
                + "    public void save(Owner o) {\n"
                + "        this.em.persist(o);\n"
                + "    }\n"
                + "}\n";
    }

    static String header(String pkg, String extraImports) {
        return "package " + pkg + ".repository;\n\n"
                + extraImports
                + "import java.util.Collection;\n\n"
                + "import io.quarkus.arc.profile.IfBuildProfile;\n"
                + "import jakarta.persistence.EntityManager;\n"
                + "import " + pkg + ".model.Owner;\n\n";
    }

    @ParameterizedTest
    @CsvSource({"org.springframework.samples.petclinic", "com.example.shop", "io.acme.depot.app"})
    void addsScopeAndTypedTogetherPreservingProfileAndBodies(String pkg) {
        Report r = new Report();
        rewriteRun(spec -> spec.recipe(recipe(pkg, r)),
                with(pkg,
                java(header(pkg, "") + "@IfBuildProfile(\"spring-data-jpa\")\n" + implBody(pkg),
                        header(pkg, "").replace("import jakarta.persistence.EntityManager;\n",
                                "import jakarta.enterprise.context.ApplicationScoped;\nimport jakarta.enterprise.inject.Typed;\n"
                                        + "import jakarta.persistence.EntityManager;\n")
                                + "@ApplicationScoped\n@Typed(OwnerRepositoryImpl.class)\n@IfBuildProfile(\"spring-data-jpa\")\n"
                                + implBody(pkg),
                        s -> s.path(p(pkg, "repository/OwnerRepositoryImpl.java")))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.APPLIED);
        assertThat(r.matchedSymbols()).contains("implementation " + pkg + ".repository.OwnerRepositoryImpl");
    }

    @Test
    void addsOnlyTheMissingTypedToTheV16Form() {
        String pkg = "org.acme.inventory";
        Report r = new Report();
        String scoped = header(pkg, "import jakarta.enterprise.context.ApplicationScoped;\n") + "@ApplicationScoped\n" + implBody(pkg);
        rewriteRun(spec -> spec.recipe(recipe(pkg, r)), with(pkg,
                // AddImport's own layout puts a blank line between the jakarta block and java.util
                java(scoped, scoped.replace("import jakarta.enterprise.context.ApplicationScoped;\n",
                                "import jakarta.enterprise.context.ApplicationScoped;\nimport jakarta.enterprise.inject.Typed;\n\n")
                                .replace("@ApplicationScoped\n", "@ApplicationScoped\n@Typed(OwnerRepositoryImpl.class)\n"),
                        s -> s.path(p(pkg, "repository/OwnerRepositoryImpl.java")))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.APPLIED);
        assertThat(r.actions()).containsExactly("add @" + TYPED + "(OwnerRepositoryImpl.class)");
    }

    @Test
    void replacesATypedThatNamesTheFragment() {
        String pkg = "org.acme.inventory";
        Report r = new Report();
        String before = header(pkg, "import jakarta.enterprise.context.ApplicationScoped;\nimport jakarta.enterprise.inject.Typed;\n")
                + "@ApplicationScoped\n@Typed(OwnerRepository.class)\n" + implBody(pkg);
        rewriteRun(spec -> spec.recipe(recipe(pkg, r)), with(pkg,
                java(before, before.replace("@Typed(OwnerRepository.class)", "@Typed(OwnerRepositoryImpl.class)"),
                        s -> s.path(p(pkg, "repository/OwnerRepositoryImpl.java")))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.APPLIED);
    }

    @Test
    void alreadyInRequiredFormIsKeptAndSaysSo() {
        String pkg = "org.acme.inventory";
        Report r = new Report();
        String done = header(pkg, "import jakarta.enterprise.context.ApplicationScoped;\nimport jakarta.enterprise.inject.Typed;\n")
                + "@ApplicationScoped\n@Typed(OwnerRepositoryImpl.class)\n" + implBody(pkg);
        rewriteRun(spec -> spec.recipe(recipe(pkg, r)), with(pkg,
                java(done, s -> s.path(p(pkg, "repository/OwnerRepositoryImpl.java")))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.ALREADY);
    }

    @Test
    void refusesTheV29RoutedBackRecursionBeforeAnyEdit() {
        String pkg = "org.springframework.samples.petclinic";
        Report r = new Report();
        String recursing = "package " + pkg + ".repository;\n\n"
                + "import java.util.Collection;\n"
                + "import " + pkg + ".model.Owner;\n"
                + "import " + pkg + ".repository.springdatajpa.SpringDataOwnerRepository;\n\n"
                + "public class OwnerRepositoryImpl implements OwnerRepository {\n"
                + "    private SpringDataOwnerRepository delegate;\n"
                + "    public Owner findById(int id) { return delegate.findById(id); }\n"
                + "    public Collection<Owner> findAll() { return delegate.findAll(); }\n"
                + "    public void save(Owner o) { delegate.save(o); }\n"
                + "}\n";
        rewriteRun(spec -> spec.recipe(recipe(pkg, r)), with(pkg,
                java(recursing, s -> s.path(p(pkg, "repository/OwnerRepositoryImpl.java")))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.UNRESOLVED);
        assertThat(String.join(" ", r.reasons())).contains("routed-back recursion")
                .contains("SpringDataOwnerRepository.findById");
    }

    @Test
    void refusesADelegateTypedAsTheFragmentItself() {
        String pkg = "org.acme.inventory";
        Report r = new Report();
        String viaParent = "package " + pkg + ".repository;\n"
                + "import java.util.Collection;\nimport " + pkg + ".model.Owner;\n"
                + "public class OwnerRepositoryImpl implements OwnerRepository {\n"
                + "    private OwnerRepository repo;\n"
                + "    public Owner findById(int id) { return repo.findById(id); }\n"
                + "    public Collection<Owner> findAll() { return java.util.List.of(); }\n"
                + "    public void save(Owner o) { }\n"
                + "}\n";
        rewriteRun(spec -> spec.recipe(recipe(pkg, r)), with(pkg,
                java(viaParent, s -> s.path(p(pkg, "repository/OwnerRepositoryImpl.java")))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.UNRESOLVED);
    }

    @Test
    void anUnrelatedSameNamedTypeIsUntouched() {
        String pkg = "org.acme.inventory";
        Report r = new Report();
        String other = "package org.acme.legacy.repository;\n\npublic class OwnerRepositoryImpl implements Runnable {\n"
                + "    public void run() { }\n}\n";
        String target = header(pkg, "") + implBody(pkg);
        rewriteRun(spec -> spec.recipe(recipe(pkg, r)), with(pkg,
                java(other, s -> s.path("src/main/java/org/acme/legacy/repository/OwnerRepositoryImpl.java")),
                java(target, target.replace("import jakarta.persistence.EntityManager;\n",
                                "import jakarta.enterprise.context.ApplicationScoped;\nimport jakarta.enterprise.inject.Typed;\n"
                                        + "import jakarta.persistence.EntityManager;\n")
                                .replace("public class OwnerRepositoryImpl", "@ApplicationScoped\n@Typed(OwnerRepositoryImpl.class)\npublic class OwnerRepositoryImpl"),
                        s -> s.path(p(pkg, "repository/OwnerRepositoryImpl.java")))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.APPLIED);
    }

    @Test
    void aConflictingScopeIsNotReplaced() {
        String pkg = "org.acme.inventory";
        Report r = new Report();
        String single = header(pkg, "import jakarta.inject.Singleton;\n") + "@Singleton\n" + implBody(pkg);
        rewriteRun(spec -> spec.recipe(recipe(pkg, r)), with(pkg,
                java(single, s -> s.path(p(pkg, "repository/OwnerRepositoryImpl.java")))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.UNRESOLVED);
        assertThat(String.join(" ", r.reasons())).contains("jakarta.inject.Singleton");
    }

    @Test
    void missingTypeFactsRefuseWithoutPartialEdits() {
        String pkg = "org.acme.inventory";
        Report r = new Report();
        String unknown = "package " + pkg + ".repository;\n"
                + "import java.util.Collection;\nimport " + pkg + ".model.Owner;\nimport org.nowhere.Gone;\n"
                + "@Gone\n"
                + "public class OwnerRepositoryImpl implements OwnerRepository {\n"
                + "    private org.nowhere.Store store;\n"
                + "    public Owner findById(int id) { return store.load(id); }\n"
                + "    public Collection<Owner> findAll() { return java.util.List.of(); }\n"
                + "    public void save(Owner o) { }\n"
                + "}\n";
        rewriteRun(spec -> spec.recipe(recipe(pkg, r)).typeValidationOptions(org.openrewrite.test.TypeValidation.none()),
                with(pkg, java(unknown, s -> s.path(p(pkg, "repository/OwnerRepositoryImpl.java")))));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.UNRESOLVED);
        assertThat(String.join(" ", r.reasons())).contains("required type facts are missing");
    }

    @Test
    void anAbsentOwedImplementationIsNeverSynthesized() {
        String pkg = "org.acme.inventory";
        Report r = new Report();
        rewriteRun(spec -> spec.recipe(recipe(pkg, r)), support(pkg));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.UNRESOLVED);
        assertThat(String.join(" ", r.reasons())).contains("never synthesized");
    }

    @Test
    void aNameOutsideTheNamingContractIsRefused() {
        String pkg = "org.acme.inventory";
        Report r = new Report();
        FragmentCdiExposure off = new FragmentCdiExposure(pkg + ".repository.OwnerRepository", pkg + ".repository.OwnerDao",
                p(pkg, "repository/OwnerDao.java"), SCOPE, TYPED, r);
        rewriteRun(spec -> spec.recipe(off), support(pkg));
        assertThat(r.outcome()).isEqualTo(Report.Outcome.UNRESOLVED);
    }
}
