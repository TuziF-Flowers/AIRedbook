import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const target = resolve(
  "node_modules",
  "@lucasygu",
  "redbook",
  "dist",
  "lib",
  "cdp-cookies.js",
);
const oldCall =
  'ws.send(JSON.stringify({ id: 1, method: "Network.getAllCookies" }));';
const newCall =
  'ws.send(JSON.stringify({ id: 1, method: "Storage.getCookies" }));';

if (!existsSync(target)) {
  throw new Error(`redbook CDP module not found: ${target}`);
}

const source = readFileSync(target, "utf-8");
if (source.includes(newCall)) {
  console.log("redbook CDP compatibility patch already applied.");
} else if (source.includes(oldCall)) {
  writeFileSync(target, source.replace(oldCall, newCall), "utf-8");
  console.log("Applied redbook CDP compatibility patch for current Chrome.");
} else {
  throw new Error(
    "redbook CDP implementation changed; review the compatibility patch.",
  );
}
