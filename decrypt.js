import fs from 'fs';
import ModuleFactory from './mesh_loader.js';

async function main() {
    const inputPath = 'new_model.meshy';
    const outputPath = 'tiger_girl.glb';
    
    console.log("Loading WASM module...");
    const wasmModule = await ModuleFactory();
    console.log("WASM loaded!");
    
    // Read the encrypted meshy file
    const fileBuffer = fs.readFileSync(inputPath);
    const uint8Array = new Uint8Array(fileBuffer);
    
    console.log(`Processing ${inputPath} (size: ${uint8Array.byteLength} bytes)...`);
    const result = wasmModule.processMeshyFile(uint8Array);
    
    if (result && result.success && result.data) {
        console.log("Decrypted successfully!");
        fs.writeFileSync(outputPath, result.data);
        console.log(`Saved decrypted model to: ${outputPath} (size: ${result.data.byteLength} bytes)`);
    } else {
        console.error("Decryption failed. Result:", result);
    }
}

main().catch(console.error);
