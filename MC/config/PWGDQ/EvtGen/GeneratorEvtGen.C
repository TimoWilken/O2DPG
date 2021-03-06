R__LOAD_LIBRARY(EvtGen)
R__ADD_INCLUDE_PATH($EVTGEN_ROOT/include)

#include "EvtGenBase/EvtStdHep.hh"
#include "EvtGenBase/EvtRandomEngine.hh"
#include "EvtGenBase/EvtSimpleRandomEngine.hh" 
#include "EvtGen/EvtGen.hh"
#include "EvtGenBase/EvtParticle.hh"
#include "EvtGenBase/EvtPDL.hh"
#include "EvtGenBase/EvtParticleFactory.hh"
#include "EvtGenExternal/EvtExternalGenList.hh"
#include "EvtGenBase/EvtAbsRadCorr.hh"
#include "EvtGenBase/EvtMTRandomEngine.hh"
#include "EvtGenBase/EvtRandom.hh"
#include "EvtGenBase/EvtReport.hh"
#include "EvtGenExternal/EvtExternalGenList.hh"

enum DecayModeEvt {kEvtAll=0, kEvtBJpsiDiElectron, kEvtBJpsi, kEvtBJpsiDiMuon, kEvtBSemiElectronic, kEvtHadronicD, kEvtHadronicDWithout4Bodies, kEvtChiToJpsiGammaToElectronElectron, kEvtChiToJpsiGammaToMuonMuon, kEvtSemiElectronic, kEvtBSemiMuonic, kEvtSemiMuonic, kEvtDiElectron, kEvtDiMuon, kEvtBPsiPrimeDiMuon, kEvtBPsiPrimeDiElectron, kEvtJpsiDiMuon, kEvtPsiPrimeJpsiDiElectron, kEvtPhiKK, kEvtOmega, kEvtLambda, kEvtHardMuons, kEvtElectronEM, kEvtDiElectronEM, kEvtGammaEM, kEvtBeautyUpgrade};


namespace o2 {
namespace eventgen {
    
template<typename T>
class GeneratorEvtGen : public T
{


public:
  GeneratorEvtGen() : T() { };
  ~GeneratorEvtGen() = default;

  // overriden methods
  Bool_t Init() override { return T::Init() && InitEvtGen(); };
  Bool_t importParticles() override { return T::importParticles() && makeEvtGenDecays(); };

  // external setters
  void AddPdg(int pdg, int pos) { mPdgString.AddAt(pdg,pos); };  
  void SetSizePdg(int size) {mPdgString.Set(size); }; 
  void PrintDebug(bool deg=kTRUE){ mDebug = deg; };
  void SetDecayTable(TString decTab){ mDecayTablePath = decTab; };
  void SetForceDecay(DecayModeEvt forceDec){ mDecayMode = forceDec; };

protected:
  
  // Initialize Evtgen 
  Bool_t InitEvtGen(){
     
    if(mEvtGen) return kTRUE;
    std::cout << "EVTGEN INITIALIZATION" << std::endl;
    mEvtstdhep = new EvtStdHep();
    
#ifdef EVTGEN_CPP11
    // Use the Mersenne-Twister generator (C++11 only)
    mEng = new EvtMTRandomEngine();
#else
    mEng = new EvtSimpleRandomEngine();
#endif
    
    EvtRandom::setRandomEngine(mEng);
    
    char *decayTablePath = gSystem->ExpandPathName("$EVTGEN_ROOT/share/DECAY_2010.DEC"); //default decay table
    char *particleTablePath = gSystem->ExpandPathName("$EVTGEN_ROOT/share/evt.pdl"); //particle table
    std::list<EvtDecayBase*> extraModels;
    
    EvtExternalGenList genList;
    EvtAbsRadCorr *fRadCorrEngine = genList.getPhotosModel();
    extraModels = genList.getListOfModels();
    
    mEvtGen=new EvtGen(decayTablePath,particleTablePath,mEng,fRadCorrEngine,&extraModels);
    ForceDecay();
    if(mDecayTablePath.Contains("DEC")) mEvtGen->readUDecay(mDecayTablePath); // user decay table
    return kTRUE; 
  };
  
  // Decay particles using EvtGen and push products on std::vector mParticles
  Bool_t makeEvtGenDecays(){
    auto nparticles = T::mParticles.size();
    for (Int_t iparticle = 0; iparticle < nparticles; ++iparticle) {
      auto particle = (TParticle)T::mParticles.at(iparticle);
      if(checkPdg(particle.GetPdgCode())){
	if(mDebug) std::cout << "particles in the array (before decay): PDG "<< particle.GetPdgCode() << " STATUS " << particle.GetStatusCode() << " position in the array" << iparticle << " First daughter" << particle.GetFirstDaughter() << " Last daughter " << particle.GetLastDaughter() << std::endl;
	TLorentzVector *momentum=new TLorentzVector();
	momentum->SetPxPyPzE(particle.Px(),particle.Py(),particle.Pz(),particle.Energy()); 
	DecayEvtGen(particle.GetPdgCode(),momentum);
	if(!ImportParticlesEvtGen(iparticle)) { std::cout << "Attention: Import Particles failed" << std::endl; return kFALSE; }
	if(mDebug) std::cout << "particles in the array (after decay): PDG "<< particle.GetPdgCode() << " STATUS " << particle.GetStatusCode() << " position in the array" << iparticle << " First daughter" << particle.GetFirstDaughter() << " Last daughter " << particle.GetLastDaughter() << std::endl;
	
      }  
    }
    return kTRUE;
  }
  
  // decay particle
  void DecayEvtGen(Int_t ipart, TLorentzVector *p)
  {
    //
    //Decay a particle
    //input: pdg code and momentum of the particle to be decayed  
    //all informations about decay products are stored in mEvtstdhep 
    //
    EvtId IPART=EvtPDL::evtIdFromStdHep(ipart);
    EvtVector4R p_init(p->E(),p->Px(),p->Py(),p->Pz());
    EvtParticle *froot_part=EvtParticleFactory::particleFactory(IPART,p_init);
    mEvtGen->generateDecay(froot_part);
    mEvtstdhep->init();
    froot_part->makeStdHep(*mEvtstdhep);
    if(mDebug) froot_part->printTree(); //to print the decay chain 
    froot_part->deleteTree(); 
    return;
  }
  
  
  Bool_t ImportParticlesEvtGen(Int_t indexMother)
  {
    //
    //Input: index of mother particle in the vector of generated particles (mParticles)
    //return kTRUE if the size of mParticles is updated
    //Put all the informations about the decay products in mParticles
    //
    
    int j;
    int istat;
    int partnum;
    double px,py,pz,e;
    double x,y,z,t;
    EvtVector4R p4,x4;
    Int_t originalSize = T::mParticles.size();
    Int_t npart=mEvtstdhep->getNPart();
    // 0 -> mother particle
    T::mParticles[indexMother].SetFirstDaughter(mEvtstdhep->getFirstDaughter(0)+T::mParticles.size()-1);
    T::mParticles[indexMother].SetLastDaughter(mEvtstdhep->getLastDaughter(0)+T::mParticles.size()-1);
    T::mParticles[indexMother].SetStatusCode(11);
    if(mDebug) std::cout << "index mother " << indexMother << " first daughter "<< mEvtstdhep->getFirstDaughter(0)+T::mParticles.size()-1 << " last daughter " << mEvtstdhep->getLastDaughter(0)+T::mParticles.size()-1 << std::endl;
    for(int i=1;i<mEvtstdhep->getNPart();i++){
      int jmotherfirst=mEvtstdhep->getFirstMother(i) > 0 ? mEvtstdhep->getFirstMother(i) + originalSize - 1: mEvtstdhep->getFirstMother(i);
      int jmotherlast=mEvtstdhep->getLastMother(i) > 0 ? mEvtstdhep->getLastMother(i) + originalSize - 1 : mEvtstdhep->getLastMother(i);
      int jdaugfirst=mEvtstdhep->getFirstDaughter(i) >0 ? mEvtstdhep->getFirstDaughter(i) + originalSize - 1 : mEvtstdhep->getFirstDaughter(i);
      int jdauglast=mEvtstdhep->getLastDaughter(i) > 0 ? mEvtstdhep->getLastDaughter(i) + originalSize -1 : mEvtstdhep->getLastDaughter(i);
      
      if (jmotherfirst==0) jmotherfirst=indexMother; 
      if (jmotherlast==0) jmotherlast=indexMother; 
      
      partnum=mEvtstdhep->getStdHepID(i);
      
      //verify if all particles of decay chain are in the TDatabasePDG
      TParticlePDG *partPDG = TDatabasePDG::Instance()->GetParticle(partnum);
      if(!partPDG)
	{
	  std::cout << "Particle code non known in TDatabasePDG - set pdg = 89" << std::endl;
	  partnum=89; //internal use for unspecified resonance data
	}
      
      istat=mEvtstdhep->getIStat(i);
      
      if(istat!=1 && istat!=2) std::cout << "ImportParticles: Attention unknown status code!" << std::endl;
      if(istat == 2) istat = 11; //status decayed
      
      p4=mEvtstdhep->getP4(i);
      x4=mEvtstdhep->getX4(i);
      px=p4.get(1);
      py=p4.get(2);
      pz=p4.get(3);
      e=p4.get(0);
      const Float_t kconvT=0.001/2.999792458e8; // mm/c to seconds conversion
      const Float_t kconvL=1./10; // mm to cm conversion
      // shift time / position
      x=x4.get(1)*kconvL + T::mParticles[indexMother].Vx(); //[cm]
      y=x4.get(2)*kconvL + T::mParticles[indexMother].Vy(); //[cm]
      z=x4.get(3)*kconvL + T::mParticles[indexMother].Vz(); //[cm]
      t=x4.get(0)*kconvT + T::mParticles[indexMother].T(); //[s]
      
      T::mParticles.push_back(TParticle(partnum,istat,jmotherfirst,-1,jdaugfirst,jdauglast,px,py,pz,e,x,y,z,t));
      ////	
      if(mDebug) std::cout << "   -> PDG "<< partnum << " STATUS " << istat << " position in the array" << T::mParticles.size() - 1 << " mother " << jmotherfirst << " First daughter" << jdaugfirst << " Last daughter " << jdauglast << std::endl;
    }
    if(mDebug) std::cout <<"actual size " << T::mParticles.size() << " original size " << originalSize << std::endl;
    return (T::mParticles.size() > originalSize) ? kTRUE : kFALSE; 
  }
  
  bool checkPdg(int pdgPart){
    for(int ij=0; ij<mPdgString.GetSize(); ij++) 
      {
	if( TMath::Abs(TMath::Abs(pdgPart) - mPdgString.At(ij)) < 1.e-06) return kTRUE;  
      }
    return kFALSE;
  };


  
void ForceDecay()
  {
  //
  // Intupt: none - Output: none
  // Set the decay mode to decay particles: for each case is read a 
  // different decay table. case kAll read the default decay table only   
  //
  DecayModeEvt decay = mDecayMode;
  switch(decay)
    {
     case kEvtAll: // particles decayed "naturally" according to $ALICE_ROOT/TEvtGen/EvtGen/DECAY.DEC
      break;
     case kEvtBJpsiDiElectron:
      SetDecayTable("DecayTablesEvtgen/BTOJPSITOELE.DEC");
      break;
     case kEvtBJpsi:
      SetDecayTable("DecayTablesEvtgen/BTOJPSI.DEC");
      break;
     case kEvtBJpsiDiMuon:
      SetDecayTable("DecayTablesEvtgen/BTOJPSITOMU.DEC");
      break;
     case kEvtBSemiElectronic:
      SetDecayTable("DecayTablesEvtgen/BTOELE.DEC");
      break;
     case kEvtHadronicD:
      SetDecayTable("DecayTablesEvtgen/HADRONICD.DEC");
      break;
     case kEvtHadronicDWithout4Bodies:
      SetDecayTable("DecayTablesEvtgen/HADRONICDWITHOUT4BODIES.DEC");
      break;
     case kEvtChiToJpsiGammaToElectronElectron:
      SetDecayTable("DecayTablesEvtgen/CHICTOJPSITOELE.DEC");
      break;
     case kEvtChiToJpsiGammaToMuonMuon:
      SetDecayTable("DecayTablesEvtgen/CHICTOJPSITOMUON.DEC");
      break;
     case kEvtSemiElectronic:
      SetDecayTable("DecayTablesEvtgen/BANDCTOELE.DEC");
      break;
     case kEvtBSemiMuonic:
      SetDecayTable("DecayTablesEvtgen/BTOMU.DEC");
      break;
     case kEvtSemiMuonic:
      SetDecayTable("DecayTablesEvtgen/BANDCTOMU.DEC");
      break;
     case kEvtDiElectron:
      SetDecayTable("DecayTablesEvtgen/DIELECTRON.DEC");
      break;
     case kEvtDiMuon:
      SetDecayTable("DecayTablesEvtgen/DIMUON.DEC");
      break;
     case kEvtBPsiPrimeDiMuon:
      SetDecayTable("DecayTablesEvtgen/BTOPSIPRIMETODIMUON.DEC");
      break;
     case kEvtBPsiPrimeDiElectron:
      SetDecayTable("DecayTablesEvtgen/BTOPSIPRIMETODIELECTRON.DEC");
      break;
     case kEvtJpsiDiMuon:
      SetDecayTable("DecayTablesEvtgen/JPSIDIMUON.DEC");
      break;
     case kEvtPsiPrimeJpsiDiElectron:
      SetDecayTable("DecayTablesEvtgen/PSIPRIMETOJPSITOMU.DEC");
      break;
     case kEvtPhiKK:
      SetDecayTable("DecayTablesEvtgen/PHITOK.DEC");
      break;
     case kEvtOmega:
      SetDecayTable("DecayTablesEvtgen/OMEGATOLAMBDAK.DEC");
      break;
     case kEvtLambda:
      SetDecayTable("DecayTablesEvtgen/LAMBDATOPROTPI.DEC");
      break;
     case kEvtHardMuons:
      SetDecayTable("DecayTablesEvtgen/HARDMUONS.DEC");
      break;
     case kEvtElectronEM:
      SetDecayTable("DecayTablesEvtgen/ELECTRONEM.DEC");
      break;
     case kEvtDiElectronEM:
      SetDecayTable("DecayTablesEvtgen/DIELECTRONEM.DEC");
      break;
     case kEvtGammaEM:
      SetDecayTable("DecayTablesEvtgen/GAMMAEM.DEC");
      break;
     case kEvtBeautyUpgrade:
      SetDecayTable("DecayTablesEvtgen/BEAUTYUPGRADE.DEC");
      break; 
    }
    return;
  };
  
  /// evtgen pointers
  EvtGen *mEvtGen=0x0; 
  EvtStdHep *mEvtstdhep=0x0;
  EvtRandomEngine* mEng = 0;
  // pdg particles to be decayed
  TArrayI mPdgString;
  bool mDebug = kFALSE; 
  TString mDecayTablePath;  
  DecayModeEvt mDecayMode = kEvtAll; 
};
  
}}
  
