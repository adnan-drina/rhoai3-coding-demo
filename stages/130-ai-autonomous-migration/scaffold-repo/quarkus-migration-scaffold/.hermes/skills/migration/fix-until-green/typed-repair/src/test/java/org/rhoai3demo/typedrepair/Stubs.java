package org.rhoai3demo.typedrepair;

/** API stubs the recipe tests compile against (type attribution only; no behaviour). */
final class Stubs {
    private Stubs() {
    }

    static final String[] CDI = {
        "package jakarta.enterprise.context; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) public @interface ApplicationScoped {}",
        "package jakarta.enterprise.inject; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) public @interface Typed { Class<?>[] value() default {}; }",
        "package jakarta.inject; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) public @interface Singleton {}",
        "package io.quarkus.arc.profile; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) public @interface IfBuildProfile { String value() default \"\"; }",
        "package org.springframework.data.repository; public interface Repository<T, ID> {}",
        "package jakarta.persistence; public interface EntityManager { <T> T find(Class<T> c, Object id); void persist(Object o); }",
    };

    static final String[] WEB = {
        "package org.springframework.web.util; public interface UriBuilder { UriBuilder path(String p); java.net.URI build(Object... v); }",
        "package org.springframework.web.util; public abstract class UriComponents { public abstract java.net.URI toUri(); public abstract String toUriString(); }",
        "package org.springframework.web.util; public class UriComponentsBuilder implements UriBuilder {"
            + " public UriComponentsBuilder path(String p) { return this; }"
            + " public UriComponentsBuilder queryParam(String n, Object... v) { return this; }"
            + " public UriComponents buildAndExpand(Object... v) { return null; }"
            + " public UriComponents buildAndExpand(java.util.Map<String, ?> v) { return null; }"
            + " public java.net.URI build(Object... v) { return null; }"
            + " public UriComponents build() { return null; } }",
        "package org.springframework.http; public class HttpHeaders { public void setLocation(java.net.URI u) {} }",
        "package org.springframework.web.bind.annotation; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) public @interface PostMapping { String[] value() default {}; }",
        "package org.springframework.web.bind.annotation; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) public @interface RequestBody {}",
        "package jakarta.ws.rs.core; import java.lang.annotation.*; @Retention(RetentionPolicy.RUNTIME) public @interface Context {}",
        "package jakarta.ws.rs.core; public interface UriBuilder { UriBuilder path(String p); java.net.URI build(Object... v); }",
        "package jakarta.ws.rs.core; public interface UriInfo { UriBuilder getBaseUriBuilder(); }",
        "package com.other.web; public class UriComponentsBuilder { public UriComponentsBuilder path(String p) { return this; } }",
    };
}
