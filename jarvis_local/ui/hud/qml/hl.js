.pragma library

// Resaltado ligero e independiente del lenguaje: comentarios, cadenas, números
// y un conjunto común de palabras clave. No es un lexer real; basta para que un
// bloque de código se lea como código y no como texto plano.
var KEYWORDS = [
    "def","class","return","if","elif","else","for","while","in","not","and","or",
    "import","from","as","with","try","except","finally","raise","yield","lambda",
    "None","True","False","self","async","await","pass","break","continue","global",
    "const","let","var","function","=>","new","typeof","instanceof","this","export",
    "public","private","static","void","int","float","bool","str","func","package",
    "type","struct","interface","map","range","nil","fn","use","match","impl","pub"
];

function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function highlight(code, colors) {
    // colors: { kw, str, com, num, txt }
    var out = "";
    var i = 0, n = code.length;
    var kwRe = new RegExp("^(" + KEYWORDS.join("|").replace(/[+.]/g, "\\$&") + ")\\b");
    while (i < n) {
        var c = code[i];
        var rest = code.slice(i);

        // comentarios de línea  #...  //...
        var mCom = rest.match(/^(#|\/\/)[^\n]*/);
        if (mCom) { out += span(colors.com, esc(mCom[0])); i += mCom[0].length; continue; }
        // comentario de bloque /* ... */
        var mBlk = rest.match(/^\/\*[\s\S]*?\*\//);
        if (mBlk) { out += span(colors.com, esc(mBlk[0])); i += mBlk[0].length; continue; }
        // cadenas  "..."  '...'  `...`
        var mStr = rest.match(/^("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)/);
        if (mStr) { out += span(colors.str, esc(mStr[0])); i += mStr[0].length; continue; }
        // números
        var mNum = rest.match(/^\b\d[\d_]*(\.\d+)?\b/);
        if (mNum) { out += span(colors.num, esc(mNum[0])); i += mNum[0].length; continue; }
        // identificador / palabra clave
        var mId = rest.match(/^[A-Za-z_$][\w$]*/);
        if (mId) {
            if (kwRe.test(mId[0])) out += span(colors.kw, esc(mId[0]));
            else out += esc(mId[0]);
            i += mId[0].length; continue;
        }
        out += esc(c);
        i += 1;
    }
    return out;
}

function span(color, text) {
    return '<span style="color:' + color + '">' + text + '</span>';
}
