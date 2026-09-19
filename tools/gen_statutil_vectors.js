// Generates tests/golden/java_statutil/vectors.txt with the real
// edu.cmu.cs.sb.core.StatUtil (JRE 8 + stem.jar).
//
//   jjs -cp D:/stem/stem.jar gen_statutil_vectors.js
//
// The grid pins binomialtail boundary semantics (spec 03 §1.6): x > N -> 0,
// x < 0 / dp <= 0 / dp >= 1 -> 1, the x_orig == N quirk (x++ entering the
// formula), and ordinary interior values.  logbinomcoeff is public and is
// pinned as well.  Output lines:  BINOMTAIL\t<x>\t<N>\t<dp>\t<result>
//                             or  LOGBINOM\t<ni>\t<N>\t<result>
var StatUtil = Java.type("edu.cmu.cs.sb.core.StatUtil");

var XS = [-1, 0, 1, 2, 5, 50, 51, 60];
var NS = [10, 50, 100];
var DPS = [0.0, 1e-9, 0.3, 0.9999, 1.0];

var out = new java.lang.StringBuilder();

for (var i = 0; i < NS.length; i++) {
  var N = NS[i];
  for (var j = 0; j < XS.length; j++) {
    var x = XS[j];
    for (var k = 0; k < DPS.length; k++) {
      var dp = DPS[k];
      // skip absurd combos: x far above N adds nothing beyond the x > N
      // boundary itself (keep one such case per N)
      if (x > N + 1) continue;
      out.append("BINOMTAIL\t")
         .append(x).append("\t").append(N).append("\t").append(dp).append("\t")
         .append(StatUtil.binomialtail(x, N, dp)).append("\n");
    }
  }
}

// logbinomcoeff over a spread of (ni, N), including ni > N and N - ni edges
var LOGN = [5, 10, 50, 100];
for (var i = 0; i < LOGN.length; i++) {
  var N = LOGN[i];
  for (var ni = -1; ni <= N + 1; ni++) {
    // Math.round keeps the loop counter printing as an integer in Nashorn
    out.append("LOGBINOM\t")
       .append(java.lang.Math.round(ni)).append("\t").append(java.lang.Math.round(N)).append("\t")
       .append(StatUtil.logbinomcoeff(ni, N)).append("\n");
  }
}

var PrintWriter = Java.type("java.io.PrintWriter");
var pw = new PrintWriter("tests/golden/java_statutil/vectors.txt", "UTF-8");
pw.print(out.toString());
pw.close();
print(out.length());
