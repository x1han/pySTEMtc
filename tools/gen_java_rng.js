// Generates reference vectors from the real java.util.Random (JRE 8, via Nashorn).
// Output lines: SEED <s> | DOUBLE <i> <v> | INTB <i> <v> | INT <i> <v>
// The DOUBLE/INTB/INT groups are drawn sequentially from one Random instance,
// so the vector files also pin down the stream interleaving order.
var seeds = [9873287, 3733246, 2211, 42];
for (var s = 0; s < seeds.length; s++) {
    var r = new java.util.Random(seeds[s]);
    print("SEED\t" + seeds[s]);
    for (var i = 0; i < 100; i++) {
        print("DOUBLE\t" + i + "\t" + r.nextDouble());
    }
    for (var i = 0; i < 50; i++) {
        print("INTB\t" + i + "\t" + r.nextInt(1000));
    }
    for (var i = 0; i < 20; i++) {
        print("INT\t" + i + "\t" + r.nextInt());
    }
}
