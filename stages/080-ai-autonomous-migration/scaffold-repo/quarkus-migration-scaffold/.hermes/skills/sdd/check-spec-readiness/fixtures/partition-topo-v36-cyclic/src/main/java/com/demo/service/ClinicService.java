package com.demo.service;

import com.demo.entity.Owner;
import com.demo.entity.Pet;
import com.demo.entity.PetType;
import com.demo.entity.Specialty;
import com.demo.entity.Vet;
import com.demo.entity.Visit;

public interface ClinicService {
    Owner findOwner(int id);
}
