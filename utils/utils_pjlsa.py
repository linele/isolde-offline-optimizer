from cern.accsoft.commons.value import ValueFactory, Type
from cern.accsoft.commons.domain import CernAccelerator
from java.util import Collections
from cern.lsa.client import ServiceLocator, ContextService, ParameterService, TrimService, SettingService
from cern.lsa.domain.settings import TrimRequest, ContextSettingsRequest, Settings, StandAloneContextsRequest, StandAloneBeamProcessesRequest

import pjlsa
#with pjlsa.LSAClient(server="isolde").java_api():
#    from cernml.

def set_scalar(field, value) -> None:
    """Copied from https://gitlab.cern.ch/scripting-tools/pjlsa
    Allows pjlsa set scalar."""
    trimService = ServiceLocator.getService(TrimService)
    parameterService = ServiceLocator.getService(ParameterService)
    contextService = ServiceLocator.getService(ContextService)

    # Device name and value to set
    parameter = parameterService.findParameterByName(field)

    #isolde_cycle = contextService.findResidentNonMultiplexedContext(CernAccelerator.ISOLDE)
    resident_bps = contextService.findStandAloneBeamProcesses(
        StandAloneBeamProcessesRequest.builder().resident(True).particleTransfers(
            parameter.getParticleTransfers()).build())
    if not resident_bps:
        raise ValueError(f"No resident BeamProcess found for {field}")
    resident_bps = list(resident_bps)
    trim = TrimRequest.builder()
    trim.setContext(resident_bps[0])#isolde_cycle
    trim.setDescription("GeOFF optimization")
    trim.setTransient(True)
    trim.addScalar(parameter, ValueFactory.createScalar(value, Type.FLOAT))

    trimService.trimSettings(trim.build())

set_scalar("YOL2.DEH1/Setting#ccv1", 1.0)

def get_scalar(field) -> float:
    contextService = ServiceLocator.getService(ContextService)
    parameterService = ServiceLocator.getService(ParameterService)
    settingService = ServiceLocator.getService(SettingService)

    parameter = parameterService.findParameterByName(field)
    #isolde_cycle = contextService.findResidentNonMultiplexedContext(CernAccelerator.ISOLDE)
    #cycleSettings = settingService.findContextSettings(ContextSettingsRequest.byStandAloneContextAndParameters(isolde_cycle, Collections.singleton(parameter)))
    #scalar = Settings.getScalar(cycleSettings, parameter)
    resident_bps = contextService.findStandAloneBeamProcesses(
        StandAloneBeamProcessesRequest.builder().resident(True).particleTransfers(
            parameter.getParticleTransfers()).build())
    if not resident_bps:
        raise ValueError(f"No resident BeamProcess found for {field}")
    resident_bps = list(resident_bps)
    cycleSettings = settingService.findContextSettings(ContextSettingsRequest.byStandAloneContextAndParameters(resident_bps[0], Collections.singleton(parameter)))
    scalar = Settings.getScalar(cycleSettings, parameter)
    return scalar

"""def set_function(field, value) -> None:

    trimService = ServiceLocator.getService(TrimService)
    parameterService = ServiceLocator.getService(ParameterService)
    contextService = ServiceLocator.getService(ContextService)

    isolde_cycle = contextService.findResidentNonMultiplexedContext(CernAccelerator.ISOLDE)
    parameter = parameterService.findParameterByName(field)
    function = ValueFactory.createFunction(
        [0.0, 5000.0, 6000.0, 7000.0, 9240.0],
        [0.0, 0.0, 1e-5, -1e-5, 0.0]
    )
    trimRequest = TrimRequest.builder() \
        .setContext(isolde_cycle) \
        .addFunction(parameter, function) \
        .setDescription("GeOFF optimization") \
        .setTransient(True) \
        .build()
    trimService.trimSettings(trimRequest)

def get_function(field) -> None:
    contextService = ServiceLocator.getService(ContextService)
    parameterService = ServiceLocator.getService(ParameterService)
    settingService = ServiceLocator.getService(SettingService)

    parameter = parameterService.findParameterByName(field)
    isolde_cycle = contextService.findResidentNonMultiplexedContext(CernAccelerator.ISOLDE)
    cycleSettings = settingService.findContextSettings(ContextSettingsRequest.byStandAloneContextAndParameters(isolde_cycle, Collections.singleton(parameter)))

    function = Settings.getFunctionList(cycleSettings, parameter)
    func1 = ValueFactory.createFunction([0.0], [30.0])
    func2 = ValueFactory.createFunction([0.0, 0.005], [30.0, -20.0])
    func3 = ValueFactory.createFunction([0.0, 0.005], [-20.0, 30.0])
    func4 = [func1, func2, func3, func1]
    func5 = ValueFactory.createDiscreteFunctionList(func4)

    print(function)

    print(func5)"""

