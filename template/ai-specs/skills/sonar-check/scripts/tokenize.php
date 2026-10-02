<?php
/**
 * Emits normalized CPD tokens for every file listed on stdin (one path per line),
 * as "<line>\t<token>" rows separated by a "#FILE\t<path>" header.
 *
 * Mirrors what SonarPHP feeds its copy-paste detector: whitespace, comments and
 * doc comments are dropped, and string/number literals collapse to a single
 * placeholder so that a copied block with different literals still matches.
 */
$skip = [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT, T_OPEN_TAG, T_CLOSE_TAG, T_INLINE_HTML];
$literals = [T_CONSTANT_ENCAPSED_STRING, T_LNUMBER, T_DNUMBER, T_ENCAPSED_AND_WHITESPACE];

$out = [];
while (($entry = fgets(STDIN)) !== false) {
    $entry = trim($entry);
    if ($entry === '') {
        continue;
    }
    // "<label>\t<path on disk>" -- the label is what the caller wants reported.
    [$label, $path] = array_pad(explode("\t", $entry, 2), 2, null);
    $path = $path ?? $label;
    if (!is_readable($path)) {
        continue;
    }

    $tokens = @token_get_all(file_get_contents($path));
    if ($tokens === false) {
        continue;
    }

    $out[] = "#FILE\t" . $label;
    foreach ($tokens as $token) {
        if (is_array($token)) {
            [$id, $text, $line] = $token;
            if (in_array($id, $skip, true)) {
                continue;
            }
            $out[] = $line . "\t" . (in_array($id, $literals, true) ? '$LIT' : $text);
            continue;
        }
        $out[] = $line . "\t" . $token;
    }
}

echo implode("\n", $out), "\n";
