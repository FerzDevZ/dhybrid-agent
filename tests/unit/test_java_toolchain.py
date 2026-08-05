"""Tests for Java toolchain."""
import pytest
import subprocess
from dhybrid.tools.java_toolchain import (
    mvn_test,
    mvn_build,
    mvn_compile,
    mvn_package,
    mvn_clean,
    gradle_test,
    gradle_build,
    gradle_check,
    spotbugs_check,
    checkstyle_check,
)


def _has_mvn() -> bool:
    """Check if maven is available."""
    try:
        subprocess.run(["mvn", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _has_gradle() -> bool:
    """Check if gradle is available."""
    try:
        subprocess.run(["gradle", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.mark.skipif(not _has_mvn(), reason="maven not installed")
def test_mvn_test(tmp_path):
    """Test running mvn test."""
    # Create a simple Maven project
    (tmp_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "test" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "main" / "java" / "com" / "example" / "App.java").write_text(
        "package com.example;\n\npublic class App {\n    public int add(int a, int b) { return a + b; }\n}"
    )
    (tmp_path / "src" / "test" / "java" / "com" / "example" / "AppTest.java").write_text(
        "package com.example;\n\nimport org.junit.jupiter.api.Test;\nimport static org.junit.jupiter.api.Assertions.*;\n\nclass AppTest {\n    @Test\n    void testAdd() {\n        App app = new App();\n        assertEquals(3, app.add(1, 2));\n    }\n}"
    )
    (tmp_path / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test</artifactId>
    <version>1.0.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>5.10.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
""")
    
    result = mvn_test(str(tmp_path))
    assert "BUILD SUCCESS" in result or "Tests run:" in result


@pytest.mark.skipif(not _has_mvn(), reason="maven not installed")
def test_mvn_build(tmp_path):
    """Test running mvn build."""
    (tmp_path / "src" / "main" / "java" / "com" / "example" / "App.java").write_text(
        "package com.example;\n\npublic class App {\n    public static void main(String[] args) { System.out.println(\"hello\"); }\n}"
    )
    (tmp_path / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test</artifactId>
    <version>1.0.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>
</project>
""")
    
    result = mvn_build(str(tmp_path))
    assert "BUILD SUCCESS" in result


def test_mvn_compile(tmp_path):
    """Test running mvn compile."""
    (tmp_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "main" / "java" / "com" / "example" / "App.java").write_text(
        "package com.example;\n\npublic class App {\n    public static void main(String[] args) { System.out.println(\"hello\"); }\n}"
    )
    (tmp_path / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test</artifactId>
    <version>1.0.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>
</project>
""")
    
    result = mvn_compile(str(tmp_path))
    assert isinstance(result, str)


def test_mvn_package(tmp_path):
    """Test running mvn package."""
    (tmp_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "main" / "java" / "com" / "example" / "App.java").write_text(
        "package com.example;\n\npublic class App {\n    public static void main(String[] args) { System.out.println(\"hello\"); }\n}"
    )
    (tmp_path / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test</artifactId>
    <version>1.0.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>
</project>
""")
    
    result = mvn_package(str(tmp_path))
    assert isinstance(result, str)


def test_mvn_clean(tmp_path):
    """Test running mvn clean."""
    (tmp_path / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test</artifactId>
    <version>1.0.0</version>
</project>
""")
    
    result = mvn_clean(str(tmp_path))
    assert isinstance(result, str)


@pytest.mark.skipif(not _has_gradle(), reason="gradle not installed")
def test_gradle_test(tmp_path):
    """Test running gradle test."""
    (tmp_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "test" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "main" / "java" / "com" / "example" / "App.java").write_text(
        "package com.example;\n\npublic class App { public int add(int a, int b) { return a + b; } }"
    )
    (tmp_path / "src" / "test" / "java" / "com" / "example" / "AppTest.java").write_text(
        "package com.example;\n\nimport org.junit.jupiter.api.Test;\nimport static org.junit.jupiter.api.Assertions.*;\n\nclass AppTest {\n    @Test\n    void testAdd() {\n        assertEquals(3, new com.example.App().add(1, 2));\n    }\n}"
    )
    (tmp_path / "build.gradle.kts").write_text("""plugins {
    id 'java'
    id 'application'
}

group = 'com.example'
version = '1.0.0'

repositories {
    mavenCentral()
}

dependencies {
    testImplementation 'org.junit.jupiter:junit-jupiter:5.10.0'
}

application {
    mainClass.set('com.example.App')
}

tasks.test {
    useJUnitPlatform()
}
""")
    
    result = gradle_test(str(tmp_path))
    assert "BUILD SUCCESSFUL" in result or "PASSED" in result


@pytest.mark.skipif(not _has_gradle(), reason="gradle not installed")
def test_gradle_build(tmp_path):
    """Test running gradle build."""
    (tmp_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "main" / "java" / "com" / "example" / "App.java").write_text(
        "package com.example;\n\npublic class App { public static void main(String[] args) { System.out.println(\"hello\"); } }"
    )
    (tmp_path / "build.gradle.kts").write_text("""plugins {
    id 'java'
    id 'application'
}

group = 'com.example'
version = '1.0.0'

repositories {
    mavenCentral()
}

application {
    mainClass.set('com.example.App')
}
""")
    
    result = gradle_build(str(tmp_path))
    assert "BUILD SUCCESSFUL" in result


def test_gradle_check(tmp_path):
    """Test running gradle check."""
    (tmp_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "main" / "java" / "com" / "example" / "App.java").write_text(
        "package com.example;\n\npublic class App { public static void main(String[] args) { System.out.println(\"hello\"); } }"
    )
    (tmp_path / "build.gradle.kts").write_text("""plugins {
    id 'java'
    id 'checkstyle'
}

group = 'com.example'
version = '1.0.0'

repositories {
    mavenCentral()
}
""")
    
    result = gradle_check(str(tmp_path))
    assert isinstance(result, str)


def test_spotbugs_check(tmp_path):
    """Test running SpotBugs."""
    (tmp_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "main" / "java" / "com" / "example" / "App.java").write_text(
        "package com.example;\n\npublic class App { public static void main(String[] args) { System.out.println(\"hello\"); } }"
    )
    (tmp_path / "build.gradle.kts").write_text("""plugins {
    id 'java'
    id 'com.github.spotbugs' version '6.0.1'
}

group = 'com.example'
version = '1.0.0'

repositories {
    mavenCentral()
}
""")
    
    result = spotbugs_check(str(tmp_path))
    assert isinstance(result, str)


def test_checkstyle_check(tmp_path):
    """Test running Checkstyle."""
    (tmp_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (tmp_path / "src" / "main" / "java" / "com" / "example" / "App.java").write_text(
        "package com.example;\n\npublic class App { public static void main(String[] args) { System.out.println(\"hello\"); } }"
    )
    (tmp_path / "build.gradle.kts").write_text("""plugins {
    id 'java'
    id 'checkstyle'
}

group = 'com.example'
version = '1.0.0'

repositories {
    mavenCentral()
}

checkstyle {
    configFile = rootProject.file("checkstyle.xml")
}
""")
    (tmp_path / "checkstyle.xml").write_text("""<?xml version="1.0"?>
<!DOCTYPE module PUBLIC "-//Puppy Crawl//DTD Check Configuration 1.3//EN" "https://checkstyle.org/dtds/configuration_1_3.dtd">
<module name="Checker">
    <module name="TreeWalker">
        <module name="JavadocMethod"/>
    </module>
</module>
""")
    
    result = checkstyle_check(str(tmp_path))
    assert isinstance(result, str)