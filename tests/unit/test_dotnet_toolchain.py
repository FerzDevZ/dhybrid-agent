"""Tests for C#/.NET toolchain."""
import pytest
import subprocess
from dhybrid.tools.dotnet_toolchain import (
    dotnet_test,
    dotnet_build,
    dotnet_restore,
    dotnet_clean,
    dotnet_fmt,
    dotnet_format,
    dotnet_tool_install,
    dotnet_outdated,
    dotnet_ef_migrations,
)


def _has_dotnet() -> bool:
    """Check if dotnet is available."""
    try:
        subprocess.run(["dotnet", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.mark.skipif(not _has_dotnet(), reason="dotnet not installed")
def test_dotnet_test(tmp_path):
    """Test running dotnet test."""
    # Create a simple .NET project
    (tmp_path / "TestProject").mkdir()
    (tmp_path / "TestProject" / "TestProject.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <IsPackable>false</IsPackable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.8.0" />
    <PackageReference Include="xunit" Version="2.6.2" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.4" />
  </ItemGroup>
</Project>
""")
    (tmp_path / "TestProject" / "UnitTest1.cs").write_text("""using Xunit;

namespace TestProject
{
    public class UnitTest1
    {
        [Fact]
        public void Test1()
        {
            Assert.Equal(3, 1 + 2);
        }
    }
}
""")
    
    result = dotnet_test(str(tmp_path / "TestProject"))
    assert "Passed" in result or "passed" in result.lower()


@pytest.mark.skipif(not _has_dotnet(), reason="dotnet not installed")
def test_dotnet_build(tmp_path):
    """Test running dotnet build."""
    (tmp_path / "TestProject").mkdir()
    (tmp_path / "TestProject" / "TestProject.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
</Project>
""")
    (tmp_path / "TestProject" / "Program.cs").write_text("""using System;

namespace TestProject
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("Hello World!");
        }
    }
}
""")
    
    result = dotnet_build(str(tmp_path / "TestProject"))
    assert "Build succeeded" in result or "Build succeeded" in result


def test_dotnet_restore(tmp_path):
    """Test running dotnet restore."""
    (tmp_path / "TestProject").mkdir()
    (tmp_path / "TestProject.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
</Project>
""")
    
    result = dotnet_restore(str(tmp_path))
    assert isinstance(result, str)


def test_dotnet_clean(tmp_path):
    """Test running dotnet clean."""
    (tmp_path / "TestProject").mkdir()
    (tmp_path / "TestProject.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
</Project>
""")
    
    result = dotnet_clean(str(tmp_path))
    assert isinstance(result, str)


def test_dotnet_fmt(tmp_path):
    """Test running dotnet format."""
    (tmp_path / "TestProject").mkdir()
    (tmp_path / "TestProject.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
</Project>
""")
    (tmp_path / "Program.cs").write_text("using System; class Program { static void Main(){Console.WriteLine(\"Hello\");}}")
    
    result = dotnet_fmt(str(tmp_path))
    assert isinstance(result, str)


def test_dotnet_format(tmp_path):
    """Test running dotnet format (alias for dotnet format)."""
    (tmp_path / "TestProject").mkdir()
    (tmp_path / "TestProject.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
</Project>
""")
    (tmp_path / "Program.cs").write_text("using System; class Program { static void Main(){Console.WriteLine(\"Hello\");}}")
    
    result = dotnet_format(str(tmp_path))
    assert isinstance(result, str)


@pytest.mark.skipif(not _has_dotnet(), reason="dotnet not installed")
def test_dotnet_tool_install(tmp_path):
    """Test running dotnet tool install."""
    result = dotnet_tool_install("dotnet-ef", "--version", "8.0.0")
    assert isinstance(result, str)


def test_dotnet_outdated(tmp_path):
    """Test running dotnet outdated."""
    (tmp_path / "TestProject.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
</Project>
""")
    
    result = dotnet_outdated(str(tmp_path))
    assert isinstance(result, str)


@pytest.mark.skipif(not _has_dotnet(), reason="dotnet not installed")
def test_dotnet_ef_migrations(tmp_path):
    """Test running dotnet ef migrations."""
    (tmp_path / "TestProject").mkdir()
    (tmp_path / "TestProject" / "TestProject.csproj").write_text("""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="8.0.0" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite" Version="8.0.0" />
  </ItemGroup>
</Project>
""")
    
    result = dotnet_ef_migrations(str(tmp_path / "TestProject"), "add InitialCreate")
    assert isinstance(result, str)