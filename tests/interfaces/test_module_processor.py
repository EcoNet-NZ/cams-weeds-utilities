"""Tests for ModuleProcessor interface and related models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.interfaces.module_processor import (
    ModuleProcessor, 
    ProcessingResult, 
    ModuleStatus
)


class TestProcessingResult:
    """Test cases for ProcessingResult Pydantic model."""
    
    def test_valid_processing_result(self):
        """Test creating a valid ProcessingResult."""
        result = ProcessingResult(
            success=True,
            records_processed=100,
            errors=[],
            metadata={"batch_size": 50},
            execution_time=15.5
        )
        
        assert result.success is True
        assert result.records_processed == 100
        assert result.errors == []
        assert result.metadata == {"batch_size": 50}
        assert result.execution_time == 15.5
    
    def test_processing_result_with_errors(self):
        """Test ProcessingResult with error messages."""
        result = ProcessingResult(
            success=False,
            records_processed=25,
            errors=["Connection timeout", "Invalid data format"],
            execution_time=10.0
        )
        
        assert result.success is False
        assert result.records_processed == 25
        assert len(result.errors) == 2
        assert "Connection timeout" in result.errors
        assert "Invalid data format" in result.errors
    
    def test_processing_result_defaults(self):
        """Test ProcessingResult with default values."""
        result = ProcessingResult(
            success=True,
            records_processed=0,
            execution_time=0.5
        )
        
        assert result.errors == []
        assert result.metadata == {}
    
    def test_negative_records_processed_invalid(self):
        """Test that negative records_processed raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ProcessingResult(
                success=True,
                records_processed=-5,
                execution_time=1.0
            )
        
        errors = exc_info.value.errors()
        assert any("greater than or equal to 0" in str(error) for error in errors)
    
    def test_negative_execution_time_invalid(self):
        """Test that negative execution_time raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ProcessingResult(
                success=True,
                records_processed=10,
                execution_time=-1.0
            )
        
        errors = exc_info.value.errors()
        assert any("greater than or equal to 0" in str(error) for error in errors)


class TestModuleStatus:
    """Test cases for ModuleStatus Pydantic model."""
    
    def test_valid_module_status(self):
        """Test creating a valid ModuleStatus."""
        last_run = datetime.now()
        status = ModuleStatus(
            module_name="spatial_field_updater",
            is_configured=True,
            last_run=last_run,
            status="ready",
            health_check=True
        )
        
        assert status.module_name == "spatial_field_updater"
        assert status.is_configured is True
        assert status.last_run == last_run
        assert status.status == "ready"
        assert status.health_check is True
    
    def test_module_status_without_last_run(self):
        """Test ModuleStatus with no last_run (None)."""
        status = ModuleStatus(
            module_name="test_module",
            is_configured=False,
            status="error",
            health_check=False
        )
        
        assert status.last_run is None
        assert status.is_configured is False
        assert status.status == "error"
    
    def test_module_status_serialization(self):
        """Test ModuleStatus model serialization."""
        status = ModuleStatus(
            module_name="test_module",
            is_configured=True,
            status="ready",
            health_check=True
        )
        
        data = status.model_dump()
        assert data["module_name"] == "test_module"
        assert data["is_configured"] is True
        assert data["last_run"] is None
        assert data["status"] == "ready"
        assert data["health_check"] is True


class TestModuleProcessor:
    """Test cases for ModuleProcessor abstract base class."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that ModuleProcessor cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            ModuleProcessor()
        
        assert "Can't instantiate abstract class" in str(exc_info.value)
    
    def test_abstract_methods_required(self):
        """Test that all abstract methods must be implemented in subclasses."""
        
        class IncompleteModule(ModuleProcessor):
            """Incomplete implementation missing abstract methods."""
            pass
        
        with pytest.raises(TypeError) as exc_info:
            IncompleteModule()
        
        error_message = str(exc_info.value)
        assert "Can't instantiate abstract class" in error_message
        
        # Check that all expected abstract methods are mentioned
        abstract_methods = ["__init__", "validate_configuration", "process", "get_status"]
        for method in abstract_methods:
            assert method in error_message
    
    def test_concrete_implementation_works(self):
        """Test that a complete implementation can be instantiated."""
        
        class ConcreteModule(ModuleProcessor):
            """Complete implementation of ModuleProcessor."""
            
            def __init__(self, config_loader):
                self.config_loader = config_loader
            
            def validate_configuration(self) -> bool:
                return True
            
            def process(self, dry_run: bool = False) -> ProcessingResult:
                return ProcessingResult(
                    success=True,
                    records_processed=10,
                    execution_time=1.0
                )
            
            def get_status(self) -> ModuleStatus:
                return ModuleStatus(
                    module_name="concrete_module",
                    is_configured=True,
                    status="ready",
                    health_check=True
                )
        
        # This should not raise an exception
        config_loader_mock = "mock_config_loader"
        module = ConcreteModule(config_loader_mock)
        
        assert module.config_loader == config_loader_mock
        assert module.validate_configuration() is True
        
        result = module.process(dry_run=True)
        assert isinstance(result, ProcessingResult)
        assert result.success is True
        
        status = module.get_status()
        assert isinstance(status, ModuleStatus)
        assert status.module_name == "concrete_module"


class TestInterfaceCompliance:
    """Test cases for interface compliance validation."""
    
    def test_processing_result_interface_compliance(self):
        """Test that ProcessingResult has expected interface."""
        # Test all required fields are present
        result = ProcessingResult(
            success=True,
            records_processed=5,
            execution_time=2.0
        )
        
        # Verify all expected attributes exist
        assert hasattr(result, 'success')
        assert hasattr(result, 'records_processed')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'metadata')
        assert hasattr(result, 'execution_time')
        
        # Verify types
        assert isinstance(result.success, bool)
        assert isinstance(result.records_processed, int)
        assert isinstance(result.errors, list)
        assert isinstance(result.metadata, dict)
        assert isinstance(result.execution_time, float)
    
    def test_module_status_interface_compliance(self):
        """Test that ModuleStatus has expected interface."""
        status = ModuleStatus(
            module_name="test",
            is_configured=True,
            status="ready",
            health_check=True
        )
        
        # Verify all expected attributes exist
        assert hasattr(status, 'module_name')
        assert hasattr(status, 'is_configured')
        assert hasattr(status, 'last_run')
        assert hasattr(status, 'status')
        assert hasattr(status, 'health_check')
        
        # Verify types
        assert isinstance(status.module_name, str)
        assert isinstance(status.is_configured, bool)
        assert status.last_run is None or isinstance(status.last_run, datetime)
        assert isinstance(status.status, str)
        assert isinstance(status.health_check, bool) 