/** Non-destructive delivery-size export. All visual generation/editing is done
 * by the host image tool. This step only scales uniformly and pads the canvas.
 * node export_canvas.mjs --plan plan.json --id main01 --source native.png
 *      --output delivery.png [--module-dir <bundled node_modules>]
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
const args = process.argv.slice(2);
const opts = {};
for (let i = 0; i < args.length; i += 2) {
  if (!args[i]?.startsWith('--') || !args[i + 1]) throw new Error('Expected --name value arguments');
  opts[args[i].slice(2)] = args[i + 1];
}
for (const name of ['plan', 'id', 'source', 'output']) if (!opts[name]) throw new Error(`Missing --${name}`);
const require = createRequire(import.meta.url);
const sharp = opts['module-dir'] ? require(path.join(opts['module-dir'], 'sharp')) : require('sharp');
const plan = JSON.parse(await fs.readFile(opts.plan, 'utf8'));
const slot = plan.images.find(x => x.id === opts.id);
if (!slot || slot.state === 'blocked') throw new Error('Unknown/blocked image slot');
if (path.resolve(opts.source) === path.resolve(opts.output)) throw new Error('Source must remain unchanged');
const metadata = await sharp(opts.source).metadata();
if (!['png', 'jpeg', 'webp'].includes(metadata.format)) throw new Error('Only raster image export is supported');
const buffer = await sharp(opts.source).rotate().resize(slot.width, slot.height, {
  fit: 'contain', background: '#ffffff', kernel: 'lanczos3'
}).flatten({background:'#ffffff'}).toColorspace('srgb').png().toBuffer();
await fs.mkdir(path.dirname(opts.output), {recursive:true});
const handle = await fs.open(opts.output, 'wx');
try { await handle.writeFile(buffer); } finally { await handle.close(); }
process.stdout.write(JSON.stringify({
  id:slot.id, source:path.resolve(opts.source), path:path.resolve(opts.output),
  native_pixels:[metadata.width,metadata.height], pixels:[slot.width,slot.height],
  operation:'uniform-scale-and-white-canvas-export',
  upscaled:slot.width>metadata.width || slot.height>metadata.height,
  sha256:createHash('sha256').update(buffer).digest('hex'),
  visual_edit:false, human_approval:'pending'
})+'\n');
