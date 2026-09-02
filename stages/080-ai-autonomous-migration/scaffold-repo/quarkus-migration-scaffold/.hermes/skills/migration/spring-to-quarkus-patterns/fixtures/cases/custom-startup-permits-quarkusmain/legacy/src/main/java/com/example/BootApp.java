package com.example;

import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class BootApp implements CommandLineRunner {
    public static void main(String[] args) {
        SpringApplication.run(BootApp.class, args);
    }

    @Override
    public void run(String... args) {
        System.out.println("seed");
    }
}
