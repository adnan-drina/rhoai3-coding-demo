FROM golang:1.25-alpine AS builder

ENV GOTOOLCHAIN=auto
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /metering-service ./cmd

FROM registry.access.redhat.com/ubi9/ubi-minimal:9.5

WORKDIR /
COPY --from=builder /metering-service /metering-service
USER 1001

ENTRYPOINT ["/metering-service"]
