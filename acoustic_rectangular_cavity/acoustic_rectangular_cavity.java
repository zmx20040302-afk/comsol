/*
 * Rectangular rigid-wall acoustic cavity verification model.
 *
 * Run from COMSOL Desktop:
 *   Developer > Java Editor, open this file, then Run.
 *
 */

import com.comsol.model.*;
import com.comsol.model.util.*;

public class acoustic_rectangular_cavity {

  public static Model run() {
    Model model = ModelUtil.create("Model");
    model.label("acoustic_rectangular_cavity.mph");

    model.param().set("Lx", "4[m]", "Cavity length");
    model.param().set("Ly", "3[m]", "Cavity width");
    model.param().set("c_air", "343[m/s]", "Speed of sound");
    model.param().set("rho_air", "1.225[kg/m^3]", "Air density");
    model.param().set("f_shift", "35[Hz]", "Eigenfrequency search shift");
    model.param().set("hmax", "c_air/(6*120[Hz])", "Maximum mesh size at 120 Hz");

    // Analytical rigid-wall rectangular-cavity eigenfrequencies.
    model.param().set("f10_ref", "c_air/(2*Lx)", "Analytical (1,0) mode");
    model.param().set("f01_ref", "c_air/(2*Ly)", "Analytical (0,1) mode");
    model.param().set(
        "f11_ref",
        "c_air/2*sqrt((1/Lx)^2+(1/Ly)^2)",
        "Analytical (1,1) mode");
    model.param().set("f20_ref", "c_air/Lx", "Analytical (2,0) mode");

    model.component().create("comp1", true);
    model.component("comp1").geom().create("geom1", 2);
    model.component("comp1").geom("geom1").lengthUnit("m");
    model.component("comp1").geom("geom1").create("r1", "Rectangle");
    model.component("comp1").geom("geom1").feature("r1")
         .set("size", new String[]{"Lx", "Ly"});
    model.component("comp1").geom("geom1").run();

    model.component("comp1").material().create("mat1", "Common");
    model.component("comp1").material("mat1").label("Air");
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("density", "rho_air");
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("soundspeed", "c_air");

    // Pressure Acoustics adds a sound-hard wall as its default boundary condition.
    model.component("comp1").physics().create("acpr", "PressureAcoustics", "geom1");

    model.component("comp1").mesh().create("mesh1");
    model.component("comp1").mesh("mesh1").create("size1", "Size");
    model.component("comp1").mesh("mesh1").feature("size1")
         .set("custom", true);
    model.component("comp1").mesh("mesh1").feature("size1")
         .set("hmax", "hmax");
    model.component("comp1").mesh("mesh1").create("ftri1", "FreeTri");
    model.component("comp1").mesh("mesh1").run();

    model.study().create("std1");
    model.study("std1").create("eig", "Eigenfrequency");
    model.study("std1").feature("eig").set("neigs", 8);
    model.study("std1").feature("eig").set("shift", "f_shift");
    model.study("std1").createAutoSequences("all");
    model.study("std1").run();

    model.result().create("pg_acoustic_test", "PlotGroup2D");
    model.result("pg_acoustic_test").label("Acoustic Pressure Eigenmode");
    model.result("pg_acoustic_test").create("surf1", "Surface");
    model.result("pg_acoustic_test").feature("surf1").set("expr", "p");
    model.result("pg_acoustic_test").feature("surf1").set("descr", "Acoustic pressure");
    model.result("pg_acoustic_test").run();

    model.save("acoustic_rectangular_cavity.mph");
    return model;
  }

  public static void main(String[] args) {
    run();
  }
}
