# Spring sorting idioms → plain Java (B9)

Use this card when a parity `order` difference names a collection whose source sorts it with a Spring utility. The brief's `order_explained` line reports what the bodies show: reversed or permuted, and the source and destination direction of each candidate key. This card gives what the source code means. Read both. When the brief reports more than one candidate key, the source call decides which one applies.

## `PropertyComparator` / `MutableSortDefinition` (spring-beans)

```java
PropertyComparator.sort(list, new MutableSortDefinition("date", false, false));
```

The constructor is `MutableSortDefinition(String property, boolean ignoreCase, boolean ascending)`. The **third** argument is `ascending`. `false` means **descending**. The call above sorts by `date`, newest first, case-sensitively. See [MutableSortDefinition 5.3.31](https://github.com/spring-projects/spring-framework/blob/v5.3.31/spring-beans/src/main/java/org/springframework/beans/support/MutableSortDefinition.java#L67).

`PropertyComparator` compares two non-null values. If one value is null, the non-null value sorts first. The whole result is then negated for a descending sort, so **nulls sort first when the order is descending**. See [PropertyComparator 5.3.31](https://github.com/spring-projects/spring-framework/blob/v5.3.31/spring-beans/src/main/java/org/springframework/beans/support/PropertyComparator.java#L102). The sort is stable, because `Collections.sort` is stable, so equal keys keep their input order.

Plain Java, with no `spring-beans` on the destination:

```java
list.sort(Comparator.comparing(Visit::getDate, Comparator.nullsLast(Comparator.<LocalDate>naturalOrder())).reversed());
// descending, nulls first -- the same order PropertyComparator(ascending=false) gives
```

Do **not** add `spring-beans` to reach `PropertyComparator`. Do **not** change the collection type to "stabilize" iteration. A `Set` field that is sorted in its getter is ordered by the sort, not by the set.

## Spring Data `Sort`

`Sort.by("date").descending()`, `Sort.by(Sort.Direction.DESC, "date")` and a derived query `...OrderByDateDesc` all mean descending by `date`. See the [Spring Data Sort API](https://docs.spring.io/spring-data/commons/docs/current/api/org/springframework/data/domain/Sort.html). On Quarkus Spring Data JPA the same repository method name is supported. In Panache, the equivalent is `Sort.by("date", Sort.Direction.Descending)`.

## What the brief cannot tell you

- **Several candidate keys.** A two-element list is sorted "the same way" by every field, so the brief reports all of them as ambiguous. The source call decides which key applies.
- **Ties.** The bodies cannot show the order among equal keys. Keep the source's stable tie order; do not invent a secondary key.
- **Unordered by contract.** Only an explicit source or API contract makes an order irrelevant. Never sort both bodies to make a comparison pass.
