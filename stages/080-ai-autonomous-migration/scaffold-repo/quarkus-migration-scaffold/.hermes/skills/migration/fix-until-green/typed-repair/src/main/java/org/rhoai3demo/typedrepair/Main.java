package org.rhoai3demo.typedrepair;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.stream.Collectors;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import org.openrewrite.ExecutionContext;
import org.openrewrite.InMemoryExecutionContext;
import org.openrewrite.Recipe;
import org.openrewrite.RecipeRun;
import org.openrewrite.Result;
import org.openrewrite.SourceFile;
import org.openrewrite.internal.InMemoryLargeSourceSet;
import org.openrewrite.java.JavaParser;
import org.openrewrite.java.tree.J;
import org.openrewrite.java.tree.JavaType;
import org.openrewrite.java.tree.TypeUtils;
import org.openrewrite.tree.ParseError;

/**
 * The typed repair executor (V26-1). It reads one request, parses the
 * candidate's sources with the candidate's own classpath, runs ONE of this
 * project's recipes on OpenRewrite's lossless semantic tree, and writes the
 * complete proposed patch and a result record into an output directory. It
 * never writes into the candidate tree: applying the patch is the caller's
 * decision after it has inspected the complete diff against the issued grant.
 *
 * <pre>java -jar typed-repair.jar --request request.json --out DIR</pre>
 *
 * Exit 0 whenever a result record was written (the outcome is in the record);
 * exit 2 on a usage error.
 */
public final class Main {

    public static final String SCHEMA = "rhoai3.typed-repair-result/v1";
    public static final String REQUEST_SCHEMA = "rhoai3.typed-repair-request/v1";
    public static final String EXECUTOR = "typed-repair";
    public static final String VERSION = "1.0.0";

    private Main() {
    }

    public static void main(String[] args) throws IOException {
        Path request = null;
        Path out = null;
        for (int i = 0; i < args.length; i++) {
            if ("--request".equals(args[i]) && i + 1 < args.length) {
                request = Paths.get(args[++i]);
            } else if ("--out".equals(args[i]) && i + 1 < args.length) {
                out = Paths.get(args[++i]);
            } else if ("--version".equals(args[i])) {
                System.out.println(EXECUTOR + " " + VERSION + " rewrite " + rewriteVersion());
                return;
            }
        }
        if (request == null || out == null) {
            System.err.println("usage: typed-repair --request request.json --out DIR");
            System.exit(2);
        }
        Map<String, Object> result = run(request, out);
        System.out.println(result.get("outcome") + " " + String.join(" | ", castList(result.get("reasons"))));
    }

    @SuppressWarnings("unchecked")
    private static List<String> castList(Object o) {
        return o instanceof List ? (List<String>) o : List.of();
    }

    static String rewriteVersion() {
        String v = JavaParser.class.getPackage().getImplementationVersion();
        return v == null ? "8.89.0" : v;
    }

    static ObjectMapper mapper() {
        return new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT)
                .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS);
    }

    public static Map<String, Object> run(Path requestFile, Path out) throws IOException {
        long t0 = System.nanoTime();
        ObjectMapper om = mapper();
        JsonNode req = om.readTree(requestFile.toFile());
        Files.createDirectories(out);
        Map<String, Object> rec = new LinkedHashMap<>();
        rec.put("schema", SCHEMA);
        rec.put("executor", Map.of("name", EXECUTOR, "version", VERSION, "rewrite_version", rewriteVersion(),
                "java_runtime", System.getProperty("java.runtime.version", "")));
        String recipeId = req.path("recipe").asText("");
        rec.put("recipe", Map.of("id", recipeId, "version", req.path("recipe_version").asText(""),
                "operation", req.path("operation").asText("")));
        Report report = new Report();
        List<Map<String, Object>> changes = new ArrayList<>();
        Map<String, Object> parse = new LinkedHashMap<>();
        Map<String, Object> symbols = new LinkedHashMap<>();
        try {
            if (!REQUEST_SCHEMA.equals(req.path("schema").asText(""))) {
                report.reason("the request is not " + REQUEST_SCHEMA);
                report.decide(Report.Outcome.FAILED);
            } else {
                execute(req, report, changes, parse, symbols, out, om);
            }
        } catch (RuntimeException | IOException | LinkageError e) {
            report.fail("the executor failed: " + e);
            changes.clear();
        }
        if (report.outcome() == null) {
            report.decide(Report.Outcome.FAILED);
            report.reason("no outcome was decided");
        }
        rec.put("outcome", report.outcome().wire);
        rec.put("reasons", report.reasons());
        rec.put("matched_symbols", report.matchedSymbols());
        rec.put("actions", report.actions());
        rec.put("changes", changes);
        rec.put("parse", parse);
        rec.put("required_symbols", symbols);
        rec.put("elapsed_ms", (System.nanoTime() - t0) / 1_000_000L);
        om.writeValue(out.resolve("result.json").toFile(), rec);
        return rec;
    }

    private static List<String> strings(JsonNode n) {
        List<String> out = new ArrayList<>();
        if (n != null && n.isArray()) {
            n.forEach(x -> out.add(x.asText()));
        }
        return out;
    }

    /** Required type facts, attributed on the candidate's OWN classpath (not the source API facts). */
    static Map<String, Boolean> requiredSymbols(List<Path> classpath, List<String> fqns) {
        Map<String, Boolean> out = new TreeMap<>();
        if (fqns.isEmpty()) {
            return out;
        }
        StringBuilder src = new StringBuilder("class TypedRepairProbe {\n");
        for (int i = 0; i < fqns.size(); i++) {
            src.append("  ").append(fqns.get(i)).append(" f").append(i).append(";\n");
        }
        src.append("}\n");
        ExecutionContext ctx = new InMemoryExecutionContext(t -> { });
        List<SourceFile> cus = JavaParser.fromJavaVersion().classpath(classpath).logCompilationWarningsAndErrors(false)
                .build().parse(ctx, src.toString()).collect(Collectors.toList());
        for (String f : fqns) {
            out.put(f, false);
        }
        if (cus.size() == 1 && cus.get(0) instanceof J.CompilationUnit) {
            J.ClassDeclaration cd = ((J.CompilationUnit) cus.get(0)).getClasses().get(0);
            int i = 0;
            for (var st : cd.getBody().getStatements()) {
                if (st instanceof J.VariableDeclarations && i < fqns.size()) {
                    JavaType t = ((J.VariableDeclarations) st).getType();
                    JavaType.FullyQualified fq = TypeUtils.asFullyQualified(t);
                    boolean ok = fq instanceof JavaType.Class && !(fq instanceof JavaType.Unknown)
                            && fqns.get(i).equals(fq.getFullyQualifiedName())
                            && ((JavaType.Class) fq).getKind() != null;
                    out.put(fqns.get(i), ok && isComplete(fq));
                    i++;
                }
            }
        }
        return out;
    }

    /** A type javac could not load has no members and no supertype: an error shell, not a fact. */
    private static boolean isComplete(JavaType.FullyQualified fq) {
        return !fq.getMethods().isEmpty() || fq.getSupertype() != null || !fq.getInterfaces().isEmpty()
                || fq.getKind() == JavaType.FullyQualified.Kind.Annotation;
    }

    private static void execute(JsonNode req, Report report, List<Map<String, Object>> changes,
                                Map<String, Object> parse, Map<String, Object> symbols, Path out, ObjectMapper om)
            throws IOException {
        Path root = Paths.get(req.path("root").asText("")).toAbsolutePath().normalize();
        List<Path> cp = strings(req.get("classpath")).stream().map(Paths::get).collect(Collectors.toList());
        List<Path> api = strings(req.get("api_classpath")).stream().map(Paths::get).collect(Collectors.toList());
        List<String> sources = strings(req.get("sources"));
        List<String> allowed = strings(req.get("allowed_paths"));
        List<String> candidates = strings(req.get("candidate_paths"));
        JsonNode target = req.path("target");

        for (Path p : cp) {
            if (!Files.isRegularFile(p) && !Files.isDirectory(p)) {
                report.reason("a classpath entry of the candidate does not exist: " + p);
            }
        }
        List<String> required;
        Recipe recipe;
        String recipeId = req.path("recipe").asText("");
        if (FragmentCdiExposure.ID.equals(recipeId)) {
            String scope = target.path("scope").asText("");
            String typed = target.path("typed").asText("");
            List<String> types = strings(target.get("types"));
            String impl = target.path("type").asText("");
            if (!types.equals(List.of(impl))) {
                report.reason("the owed @Typed types " + types + " are not exactly the implementation " + impl);
                report.decide(Report.Outcome.UNRESOLVED);
                return;
            }
            if (!"jakarta.enterprise.context.ApplicationScoped".equals(scope) || !"jakarta.enterprise.inject.Typed".equals(typed)) {
                report.reason("the resolved exposure rule (" + scope + ", " + typed + ") is not the one this recipe "
                        + "version qualifies");
                report.decide(Report.Outcome.UNRESOLVED);
                return;
            }
            String resolution = target.path("resolution").asText("owed");
            if (!"owed".equals(resolution) && !"selected".equals(resolution)) {
                report.reason("the target resolution '" + resolution + "' is neither owed nor selected");
                report.decide(Report.Outcome.UNRESOLVED);
                return;
            }
            required = List.of(scope, typed);
            recipe = new FragmentCdiExposure(target.path("parent").asText(""), impl, target.path("path").asText(""),
                    scope, typed, report, "selected".equals(resolution));
        } else if (HandlerUriParameter.ID.equals(recipeId)) {
            List<HandlerUriParameter.Site> sites = new ArrayList<>();
            for (JsonNode s : target.path("sites")) {
                sites.add(new HandlerUriParameter.Site(s.path("path").asText(""), s.path("type").asText(""),
                        s.path("member").asText(""), s.path("parameter").asText("")));
            }
            required = List.of(HandlerUriParameter.URI_INFO, HandlerUriParameter.CONTEXT, "jakarta.ws.rs.core.UriBuilder");
            recipe = new HandlerUriParameter(sites, report);
        } else {
            report.reason("no recipe " + recipeId + " in this executor");
            report.decide(Report.Outcome.NOT_APPLICABLE);
            return;
        }
        if (!report.reasons().isEmpty()) {
            report.decide(Report.Outcome.UNRESOLVED);
            return;
        }
        Map<String, Boolean> req0 = requiredSymbols(cp, required);
        symbols.put("candidate_classpath", req0);
        List<String> missing = req0.entrySet().stream().filter(e -> !e.getValue()).map(Map.Entry::getKey)
                .collect(Collectors.toList());
        if (!missing.isEmpty()) {
            report.reason("required target symbols do not resolve on the candidate's classpath: " + missing);
            report.decide(Report.Outcome.UNRESOLVED);
            return;
        }
        List<Path> full = new ArrayList<>(cp);
        full.addAll(api);   // the retired API's own jar, from the frozen source: LAST, so the candidate's classes win
        List<Path> files = sources.stream().map(root::resolve).collect(Collectors.toList());
        List<Throwable> errors = new ArrayList<>();
        ExecutionContext ctx = new InMemoryExecutionContext(errors::add);
        List<SourceFile> lst = JavaParser.fromJavaVersion().classpath(full).logCompilationWarningsAndErrors(false)
                .build().parse(files, root, ctx).collect(Collectors.toList());
        List<String> failed = new ArrayList<>();
        for (SourceFile sf : lst) {
            if (sf instanceof ParseError) {
                failed.add(sf.getSourcePath().toString());
            }
        }
        parse.put("files", lst.size());
        parse.put("failed", failed);
        for (String c : candidates) {
            if (failed.contains(c)) {
                report.reason("the candidate file " + c + " could not be parsed");
                report.decide(Report.Outcome.UNRESOLVED);
                return;
            }
        }
        parse.put("errors", errors.stream().map(String::valueOf).limit(5).collect(Collectors.toList()));
        errors.clear();
        RecipeRun run = recipe.run(new InMemoryLargeSourceSet(lst), ctx);
        List<Result> results = run.getChangeset().getAllResults();
        if (!errors.isEmpty()) {
            report.fail("the recipe raised: " + errors.get(0));
            return;
        }
        Report.Outcome o = report.outcome();
        if (o == null) {
            report.reason("the recipe decided no outcome");
            report.decide(Report.Outcome.FAILED);
            return;
        }
        if (o != Report.Outcome.APPLIED) {
            if (!results.isEmpty()) {
                report.fail("the recipe changed files although it decided " + o.wire + ": refused");
            }
            return;
        }
        if (results.isEmpty()) {
            report.fail("the recipe decided to apply but produced no edit");
            return;
        }
        Path staged = out.resolve("staged");
        StringBuilder patch = new StringBuilder();
        for (Result r : results) {
            if (r.getBefore() == null || r.getAfter() == null) {
                report.fail("the recipe created or deleted a file (" + (r.getBefore() == null ? r.getAfter()
                        : r.getBefore()).getSourcePath() + "): refused");
                changes.clear();
                return;
            }
            String rel = r.getAfter().getSourcePath().toString().replace('\\', '/');
            if (!allowed.contains(rel) || !candidates.contains(rel)) {
                report.fail("the patch touches " + rel + ", outside the issued write grant or the recipe's candidates: "
                        + "refused, nothing staged");
                changes.clear();
                return;
            }
            Path dst = staged.resolve(rel);
            Files.createDirectories(dst.getParent());
            Files.writeString(dst, r.getAfter().printAll(), StandardCharsets.UTF_8);
            String diff = r.diff();
            patch.append(diff);
            Map<String, Object> ch = new LinkedHashMap<>();
            ch.put("path", rel);
            ch.put("diff", diff);
            changes.add(ch);
        }
        Files.writeString(out.resolve("patch.diff"), patch.toString(), StandardCharsets.UTF_8);
    }
}
