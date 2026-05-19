# Extended-Criticality--Modular-Model
Role of criticality in the structure-function relationship in the human brain. Angiolelli et al. Phys Rev Research 2025. 

The code is the modular large-scale LIF  model, with spatiotemporal patterns replay and an extended critical region, as described in the paper
"The role of criticality in the structure-function relationship in the human brain" Angiolelli et al. PPR 2025. 
The model exploit empirical information to build a large-scale brain modular LIF network model, with transient replay of stored sequencial patterns of activity, and extended critical region.
Previous versions of the code (withour empirical informations and modules) are described in the papers "Information capacity of a network of spiking neurons" S. Scarpetta, A. de Candia Physica A 2020, and "Critical Behavior and Memory Function in a Model of Spiking Neurons with a Reservoir of Spatio-Temporal Patterns" in the Functional Role of Critical Dynamics in Neural Systems, Springer Series  11 S. Scarpetta 2019; Neural avalanches at the critical point between replay and non-replay of spatiotemporal patterns" S Scarpetta, A de Candia PLoS One 2013.

The program is in c++.  Use the command "make" to compile, and "./a.out" to run. The program reads the parameters of the simulation from the file "SEED". For any question and information please write to Silvia Scarpetta sscarpetta@unisa.it

