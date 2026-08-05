#!/bin/bash
# Verifikasi bahwa perintah "lihat-url-tersebut" bekerja dengan benar
# tanpa error 403 Forbidden

echo "=== VERIFICATION: lihat-url-tersebut ==="
echo ""

# Test 1: Check configuration
echo "1. Checking model configuration..."
python3 -c "
import sys
sys.path.insert(0, 'src')
from dhybrid.config import Config
from dhybrid.llm.registry import ModelRegistry
from dhybrid.dotenv import load_dotenv
load_dotenv()
cfg = Config.load()
print(f'   Model: {cfg.model.model}')
print(f'   Base URL: {cfg.model.base_url}')
if 'opencode' in cfg.model.base_url:
    print('   ✓ Using free OpenCode Zen model (no 403 risk)')
else:
    print('   ✗ WARNING: Not using free model!')
"
echo ""

# Test 2: Test web fetch directly
echo "2. Testing web_fetch directly..."
python3 -c "
import sys
sys.path.insert(0, 'src')
from dhybrid.tools.web import web_fetch
result = web_fetch('https://example.com', max_chars=200)
if 'example domain' in result.lower():
    print('   ✓ web_fetch works correctly')
else:
    print('   ✗ web_fetch failed')
"
echo ""

# Test 3: Check skill registered
echo "3. Checking skill registration..."
python3 -c "
import sys
sys.path.insert(0, 'src')
from dhybrid.skills.loader import list_skills
skills = list_skills('skills')
for sk in skills:
    if sk.name == 'lihat-url-tersebut':
        print('   ✓ lihat-url-tersebut skill registered')
        break
else:
    print('   ✗ lihat-url-tersebut skill not found')
"
echo ""

# Test 4: Check provider enable
echo "4. Checking provider enable..."
python3 -c "
import sys
sys.path.insert(0, 'src')
from dhybrid.ui.commands import _load_provider_enabled
enabled = _load_provider_enabled()
if enabled.get('OpenCode Zen (opsional, gratis)', False):
    print('   ✓ OpenCode Zen provider ENABLED')
else:
    print('   ✗ OpenCode Zen provider DISABLED')
if enabled.get('byNara', False):
    print('   ✓ byNara provider ENABLED (for escalation)')
else:
    print('   ✗ byNara provider DISABLED')
"
echo ""

echo "=== VERIFICATION COMPLETE ==="
