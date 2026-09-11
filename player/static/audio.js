// Both stems are scheduled against one hardware audio clock. Video never emits audio.
export class StemPlayer {
  constructor(onEnd) { this.onEnd=onEnd; this.offset=0; this.playing=false; this.generation=0; this.buffers=[]; }
  async unlock() {
    if (!this.ctx) {
      this.ctx=new (window.AudioContext||window.webkitAudioContext)();
      this.master=this.ctx.createGain(); this.master.gain.value=.8;
      this.limiter=this.ctx.createDynamicsCompressor();
      this.limiter.threshold.value=-1; this.limiter.knee.value=0; this.limiter.ratio.value=20;
      this.master.connect(this.limiter).connect(this.ctx.destination);
      this.gains=[this.ctx.createGain(),this.ctx.createGain()];
      this.gains.forEach(g=>g.connect(this.master));
      this.gains[0].gain.value=1; this.gains[1].gain.value=0;
    }
    await this.ctx.resume();
  }
  setLevels(backing,vocals,master) {
    if(!this.ctx)return;
    [backing,vocals].forEach((v,i)=>this.gains[i].gain.setTargetAtTime(v,this.ctx.currentTime,.015));
    this.master.gain.setTargetAtTime(master,this.ctx.currentTime,.015);
  }
  position() { return Math.min(this.duration||0, this.playing ? this.offset+Math.max(0,this.ctx.currentTime-this.started) : this.offset); }
  pause() { this.offset=this.position();this.playing=false;this.generation++;(this.sources||[]).forEach(s=>{s.onended=null;try{s.stop();}catch{}s.disconnect();});this.sources=[]; }
  clear() { this.pause(); this.buffers=[]; this.offset=0; this.duration=0; }
  load(buffers,duration) {this.clear();this.buffers=buffers;this.duration=Math.min(duration,buffers[0].duration);}
  start(offset=this.offset) {
    this.pause();
    if(!this.buffers.length)return;
    this.offset=Math.max(0,Math.min(offset,this.duration));
    if(this.offset>=this.duration)this.offset=0;
    const generation=++this.generation;
    this.started=this.ctx.currentTime+.06;
    this.sources=this.buffers.map((buffer,i)=>{
      if(!buffer)return null;
      const node=this.ctx.createBufferSource();node.buffer=buffer;node.connect(this.gains[i]);
      if(i===0)node.onended=()=>{if(this.generation===generation&&this.playing){this.offset=this.duration;this.pause();this.onEnd();}};
      node.start(this.started,this.offset,this.duration-this.offset);return node;
    }).filter(Boolean);
    this.playing=true;
  }
  seek(offset) {const playing=this.playing;this.pause();this.offset=Math.max(0,Math.min(offset,this.duration||0));if(playing&&this.offset<this.duration)this.start(this.offset);}
}
