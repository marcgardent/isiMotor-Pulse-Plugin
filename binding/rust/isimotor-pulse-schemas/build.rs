//! Generates Rust FlatBuffers bindings from fbs/*.fbs at build time, using
//! the pure-Rust `planus` compiler (no external `flatc` binary required).
//! Regenerates automatically whenever a schema file changes.

use std::{env, fs, path::PathBuf};

fn main() {
    let fbs_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("fbs");

    let mut files: Vec<PathBuf> = fs::read_dir(&fbs_dir)
        .unwrap_or_else(|e| panic!("cannot read schema directory {}: {e}", fbs_dir.display()))
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .filter(|path| path.extension().is_some_and(|ext| ext == "fbs"))
        .collect();
    files.sort();
    assert!(!files.is_empty(), "no .fbs schema files found in {}", fbs_dir.display());

    for file in &files {
        println!("cargo:rerun-if-changed={}", file.display());
    }

    let declarations = planus_translation::translate_files(&files)
        .expect("failed to parse fbs/*.fbs - see errors printed above");
    let generated = planus_codegen::generate_rust(&declarations, true)
        .expect("failed to generate Rust bindings from the parsed schemas");

    let out_dir = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR not set by cargo"));
    fs::write(out_dir.join("schema.rs"), generated).expect("failed to write generated schema.rs");
}
