const ArtifactClassifier = require('../../src/services/ingestion/artifactClassifier');
const {
  ARTIFACT_CATEGORIES,
  SUPPORT_LEVELS,
  MAX_INDIVIDUAL_FILE_SIZE_BYTES,
} = require('../../src/constants/ingestionConstants');

describe('ArtifactClassifier per Appendix G', () => {
  let classifier;

  beforeEach(() => {
    classifier = new ArtifactClassifier();
  });

  test('classifies build cache and ignored directories', () => {
    const cases = [
      'node_modules/express/index.js',
      '.git/HEAD',
      'dist/bundle.js',
      'build/main.js',
      '.venv/bin/python',
      '__pycache__/app.cpython-310.pyc',
    ];

    for (const p of cases) {
      const res = classifier.classify(p, 100);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.BUILD_CACHE_ARTIFACTS);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.IGNORED);
    }
  });

  test('classifies minified and generated artifacts', () => {
    const res1 = classifier.classify('public/bundle.min.js', 100);
    expect(res1.category).toBe(ARTIFACT_CATEGORIES.GENERATED_ARTIFACTS);
    expect(res1.supportLevel).toBe(SUPPORT_LEVELS.IGNORED);

    const res2 = classifier.classify('public/app.min.css', 100);
    expect(res2.category).toBe(ARTIFACT_CATEGORIES.GENERATED_ARTIFACTS);
    expect(res2.supportLevel).toBe(SUPPORT_LEVELS.IGNORED);

    const res3 = classifier.classify('src/index.js.map', 100);
    expect(res3.category).toBe(ARTIFACT_CATEGORIES.GENERATED_ARTIFACTS);
    expect(res3.supportLevel).toBe(SUPPORT_LEVELS.IGNORED);
  });

  test('classifies environment secrets', () => {
    const secrets = [
      '.env',
      '.env.production',
      'certs/server.pem',
      'keys/private.key',
      'id_rsa',
      'secrets.yaml',
    ];

    for (const p of secrets) {
      const res = classifier.classify(p, 50);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.ENVIRONMENT_SECRETS);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.METADATA);
    }
  });

  test('classifies dependency metadata lockfiles', () => {
    const lockfiles = [
      'package-lock.json',
      'yarn.lock',
      'pnpm-lock.yaml',
      'poetry.lock',
      'cargo.lock',
      'requirements.txt',
    ];

    for (const p of lockfiles) {
      const res = classifier.classify(p, 500);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.DEPENDENCY_METADATA);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.METADATA);
    }
  });

  test('classifies architecture assets', () => {
    const archFiles = ['docs/architecture.drawio', 'diagrams/flow.puml', 'spec.mermaid'];
    for (const p of archFiles) {
      const res = classifier.classify(p, 500);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.ARCHITECTURE_ASSETS);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.FULL);
    }
  });

  test('classifies test files', () => {
    const tests = [
      'tests/unit/app.test.js',
      'src/math.spec.ts',
      'test_ingestion.py',
    ];
    for (const p of tests) {
      const res = classifier.classify(p, 500);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.TESTS);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.FULL);
    }
  });

  test('classifies primary source code files', () => {
    const sources = [
      'src/index.js',
      'app/main.py',
      'pkg/server.go',
      'src/lib.rs',
      'src/Main.java',
      'client/App.tsx',
    ];
    for (const p of sources) {
      const res = classifier.classify(p, 500);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.SOURCE_CODE);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.FULL);
    }
  });

  test('classifies markup and UI files', () => {
    const markup = ['public/index.html', 'styles/theme.scss', 'components/Card.vue'];
    for (const p of markup) {
      const res = classifier.classify(p, 500);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.MARKUP_UI);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.FULL);
    }
  });

  test('classifies infrastructure and container configs', () => {
    const infra = ['deploy/main.tf', 'Vagrantfile', 'helm/chart.yaml'];
    for (const p of infra) {
      const res = classifier.classify(p, 500);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.INFRASTRUCTURE);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.FULL);
    }
  });

  test('classifies database artifacts', () => {
    const db = ['migrations/init.sql', 'prisma/schema.prisma'];
    for (const p of db) {
      const res = classifier.classify(p, 500);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.DATABASE_ARTIFACTS);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.FULL);
    }
  });

  test('classifies configuration files', () => {
    const config = ['tsconfig.json', 'pyproject.toml', 'settings.yaml', 'Dockerfile', 'package.json'];
    for (const p of config) {
      const res = classifier.classify(p, 500);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.CONFIGURATION);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.FULL);
    }
  });

  test('classifies documentation with partial support', () => {
    const docs = ['README.md', 'LICENSE', 'CHANGELOG.md', 'notes.txt'];
    for (const p of docs) {
      const res = classifier.classify(p, 500);
      expect(res.category).toBe(ARTIFACT_CATEGORIES.DOCUMENTATION);
      expect(res.supportLevel).toBe(SUPPORT_LEVELS.PARTIAL);
    }
  });

  test('classifies image, data, and binary artifacts', () => {
    expect(classifier.classify('assets/logo.png', 500)).toEqual({
      category: ARTIFACT_CATEGORIES.IMAGES,
      supportLevel: SUPPORT_LEVELS.METADATA,
    });
    expect(classifier.classify('data/records.csv', 500)).toEqual({
      category: ARTIFACT_CATEGORIES.DATA_FILES,
      supportLevel: SUPPORT_LEVELS.METADATA,
    });
    expect(classifier.classify('bin/app.exe', 500)).toEqual({
      category: ARTIFACT_CATEGORIES.BINARY_ARTIFACTS,
      supportLevel: SUPPORT_LEVELS.UNSUPPORTED,
    });
    expect(classifier.classify('unknown.xyz999', 500)).toEqual({
      category: ARTIFACT_CATEGORIES.UNKNOWN_UNSUPPORTED,
      supportLevel: SUPPORT_LEVELS.UNSUPPORTED,
    });
  });

  test('enforces 5 MB individual file ceiling by downgrading support level to UNSUPPORTED', () => {
    const smallFile = classifier.classify('src/big.ts', 1024 * 1024); // 1 MB
    expect(smallFile.category).toBe(ARTIFACT_CATEGORIES.SOURCE_CODE);
    expect(smallFile.supportLevel).toBe(SUPPORT_LEVELS.FULL);

    const oversizedFile = classifier.classify(
      'src/huge.ts',
      MAX_INDIVIDUAL_FILE_SIZE_BYTES + 1 // > 5 MB
    );
    expect(oversizedFile.category).toBe(ARTIFACT_CATEGORIES.SOURCE_CODE);
    expect(oversizedFile.supportLevel).toBe(SUPPORT_LEVELS.UNSUPPORTED);
  });
});
